# Admin Panel — Laboratorio AWS (Flask + RDS MySQL + S3 + Docker + EC2)

Aplicación web con perfil de administrador para gestión de usuarios (CRUD) desplegada en AWS usando contenedores Docker, base de datos RDS MySQL e imágenes en S3.

## 📋 Tabla de contenidos

1. [Arquitectura](#arquitectura)
2. [Stack](#stack)
3. [Estructura del proyecto](#estructura-del-proyecto)
4. [Prerrequisitos](#prerrequisitos)
5. [Paso 1: Crear bucket S3](#paso-1-crear-bucket-s3)
6. [Paso 2: Crear base de datos RDS MySQL](#paso-2-crear-base-de-datos-rds-mysql)
7. [Paso 3: Crear IAM Role para EC2](#paso-3-crear-iam-role-para-ec2)
8. [Paso 4: Lanzar instancia EC2](#paso-4-lanzar-instancia-ec2)
9. [Paso 5: Configurar Security Group de RDS](#paso-5-configurar-security-group-de-rds)
10. [Paso 6: Instalar Docker en EC2](#paso-6-instalar-docker-en-ec2)
11. [Paso 7: Subir el código a EC2](#paso-7-subir-el-código-a-ec2)
12. [Paso 8: Configurar el archivo .env](#paso-8-configurar-el-archivo-env)
13. [Paso 9: Construir y arrancar el contenedor](#paso-9-construir-y-arrancar-el-contenedor)
14. [Imagen Docker en Docker Hub](#imagen-docker-en-docker-hub)
15. [Pruebas funcionales](#pruebas-funcionales)
16. [Buenas prácticas de seguridad aplicadas](#buenas-prácticas-de-seguridad-aplicadas)
17. [Evidencias requeridas](#evidencias-requeridas)
18. [Troubleshooting](#troubleshooting)
19. [Limpiar recursos](#limpiar-recursos)

---

## Arquitectura

```
        ┌────────────────────┐
        │   Docker Hub       │
        │  imagen publicada  │──── docker pull ──┐
        └────────────────────┘                   │
                                                 │
                    ┌──────────────────┐         │
                    │   Navegador      │         │
                    │   (Admin)        │         │
                    └────────┬─────────┘         │
                             │ HTTP (puerto 80)  │
                             ▼                   ▼
        ┌────────────────────────────────────────┐
        │   EC2 t2.micro (Amazon Linux 2023)     │
        │   ┌──────────────────────────────┐     │
        │   │  Docker Container            │     │
        │   │  Flask + Gunicorn :5000      │     │
        │   └──────────────────────────────┘     │
        │   IAM Role: EC2-AdminPanel-Role        │
        │   (acceso a S3 sin credenciales)       │
        └──────┬──────────────────────┬──────────┘
               │ MySQL (3306)         │ HTTPS S3 API
               ▼                      ▼
        ┌──────────────┐      ┌──────────────────┐
        │  RDS MySQL   │      │   S3 Bucket      │
        │  privada     │      │   profiles/*.jpg │
        │  (SG: solo   │      │   (lectura       │
        │   EC2)       │      │    pública)      │
        └──────────────┘      └──────────────────┘
```

## Stack

- **Backend:** Python 3.12, Flask 3, SQLAlchemy, Flask-Login
- **Servidor WSGI:** Gunicorn (3 workers)
- **Base de datos:** Amazon RDS MySQL 8
- **Storage:** Amazon S3
- **Contenedor:** Docker
- **Host:** EC2 (Amazon Linux 2023, t2.micro/t3.micro free tier)

## Estructura del proyecto

```
lab-aws-flask/
├── app/
│   ├── __init__.py          # Factory de Flask, config DB
│   ├── auth.py              # Login/logout admin
│   ├── routes.py            # CRUD de usuarios
│   ├── models.py            # Modelos Admin, User
│   ├── s3_utils.py          # Subir/borrar imágenes en S3
│   ├── templates/           # HTML (Jinja2)
│   └── static/style.css
├── run.py                   # Entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Prerrequisitos

- Cuenta AWS personal con permisos para crear RDS, EC2, S3, IAM.
- Par de claves SSH (`.pem`) descargado al crear la EC2.
- Git instalado localmente (opcional, para clonar desde GitHub).
- Cliente SSH (Windows: PowerShell con OpenSSH, Git Bash o PuTTY).

---

## Paso 1: Crear bucket S3

1. Consola AWS → **S3** → **Crear bucket**.
2. **Nombre del bucket:** debe ser único globalmente. Ej: `mi-bucket-perfiles-lab` o agregando un sufijo único.
3. **Región:** `us-east-1` (o la que prefieras — todos los recursos deben estar en la misma región).
4. **Configuración de bloqueo de acceso público:** ⚠️ **DESMARCA "Bloquear todo el acceso público"**. Confirma con el checkbox de advertencia.
5. **Control de versiones:** deshabilitado.
6. **Cifrado por defecto:** déjalo activado (SSE-S3).
7. Click en **Crear bucket**.

### Aplicar política de lectura pública para las imágenes

Sin esto, las imágenes no se verán ni en la app ni en el navegador.

1. Click en tu bucket → pestaña **Permisos**.
2. Sección **Política del bucket** → **Editar**.
3. Pega esto reemplazando `NOMBRE-DE-TU-BUCKET`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadProfiles",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::NOMBRE-DE-TU-BUCKET/profiles/*"
    }
  ]
}
```

4. Click en **Guardar cambios**.

📸 **Evidencias:**
- `01_S3_bucket_creado.png`: bucket en la lista.
- `02_S3_policy.png`: la política JSON aplicada.

---

## Paso 2: Crear base de datos RDS MySQL

1. Consola AWS → **RDS** → **Crear base de datos**.
2. **Método de creación:** Creación estándar.
3. **Motor:** MySQL (versión por defecto 8.0.xx).
4. **Plantilla:** Capa gratuita.
5. **Settings (Configuración):**
   - Identificador de instancia: `adminpanel-db`
   - Usuario maestro: `admin`
   - Contraseña maestra: anótala (será tu `DB_PASSWORD`).
6. **Configuración de instancia:** Clases ampliables → `db.t3.micro` o `db.t4g.micro`.
7. **Almacenamiento:** 20 GB gp3. Desmarca "Autoescalado de almacenamiento".
8. **Conectividad:**
   - Recurso de computación: **No conectar con una EC2**.
   - VPC: Default.
   - **Acceso público:** **Sí** (necesario si quieres conectarte desde tu PC para evidencias; si no, puedes poner No).
   - Grupo de seguridad: **Crear nuevo** → nombre `rds-sg`.
   - Zona de disponibilidad: Sin preferencia.
   - Puerto: 3306.
9. **Autenticación:** autenticación con contraseña.
10. **Supervisión:** desmarca "Performance Insights" y "Supervisión mejorada" (ahorra costos).
11. **Configuración adicional (¡expándela!):**
    - **Nombre de base de datos inicial:** `adminpanel` ⚠️ **No lo dejes vacío**.
    - Desmarca "Habilitar copias de seguridad automatizadas".
    - **Habilitar la protección contra eliminación:** desmárcala.
12. Click en **Crear base de datos**. Tarda 5-10 min en pasar a "Disponible".

### Obtener el endpoint

Cuando esté **Disponible**:
1. Click en `adminpanel-db`.
2. Pestaña **Conectividad y seguridad** → busca el campo **Punto de enlace (endpoint)**.
3. Es una URL del tipo: `adminpanel-db.xxxxx.us-east-1.rds.amazonaws.com`.
4. Anótalo — será tu `DB_HOST` en el `.env`.

> En la nueva interfaz de AWS, el endpoint puede aparecer dentro de la sección **"Conectarse mediante → Puntos de conexión"** y aparecer etiquetado como "Nombre de la BD".

📸 **Evidencia:** `04_RDS_disponible.png` mostrando estado "Disponible" y endpoint.

---

## Paso 3: Crear IAM Role para EC2

Este rol permite que la EC2 acceda a S3 sin almacenar claves AWS en el código (buena práctica de seguridad clave).

1. Consola AWS → **IAM** → **Roles** → **Crear rol**.
2. **Tipo de entidad de confianza:** Servicio de AWS.
3. **Caso de uso:** EC2.
4. **Permisos:** elige una opción:

   **Opción A (rápida pero amplia):** busca y selecciona `AmazonS3FullAccess`.

   **Opción B (más segura — principio de mínimo privilegio):** crea una política inline:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject",
           "s3:DeleteObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::NOMBRE-DE-TU-BUCKET",
           "arn:aws:s3:::NOMBRE-DE-TU-BUCKET/*"
         ]
       }
     ]
   }
   ```

5. **Nombre del rol:** `EC2-AdminPanel-Role`.
6. **Crear rol**.

📸 **Evidencia:** `05_IAM_role.png` mostrando el rol con la política adjunta.

---

## Paso 4: Lanzar instancia EC2

1. Consola AWS → **EC2** → **Lanzar instancias**.
2. **Nombre:** `admin-panel-server`.
3. **AMI:** Amazon Linux 2023 (capa gratuita).
4. **Tipo:** `t2.micro` o `t3.micro` (capa gratuita).
5. **Par de claves:** crea uno nuevo (`lab-aws-key`, formato `.pem`) y **guárdalo bien** — no se puede volver a descargar.
6. **Configuración de red → Editar:**
   - Crear nuevo grupo de seguridad: `ec2-sg`.
   - Reglas de entrada:
     - **SSH (22)** desde **Mi IP**.
     - **HTTP (80)** desde `0.0.0.0/0`.
7. **Almacenamiento:** 8 GB gp3.
8. **Detalles avanzados → Perfil de instancia de IAM:** selecciona `EC2-AdminPanel-Role`. ⚠️ Si no aparece, refresca la página.
9. **Lanzar instancia**.

Espera a que el estado sea **En ejecución** y **Checks 2/2**. Anota la **Dirección IPv4 pública**.

📸 **Evidencia:** `06_EC2_instancia.png` con IP pública e indicador de rol IAM adjunto.

---

## Paso 5: Configurar Security Group de RDS

Ahora restringimos el acceso a RDS solo desde la EC2.

1. EC2 → **Grupos de seguridad** → click en `rds-sg`.
2. Pestaña **Reglas de entrada** → **Editar reglas de entrada**.
3. **Elimina** la regla existente (si tiene origen `0.0.0.0/0`).
4. **Agregar regla:**
   - Tipo: MySQL/Aurora
   - Puerto: 3306
   - Origen: **Personalizado** → selecciona el SG de tu EC2 (`ec2-sg` o `launch-wizard-X` según el nombre que se haya generado).
5. Guardar reglas.

> ⚠️ El campo "Origen" necesita el **ID** del SG (`sg-xxxxx`), no el nombre. Si lo escribes a mano se pone rojo. Haz click dentro del campo para que aparezca el desplegable y selecciónalo desde ahí.

📸 **Evidencia:** `07_SG_RDS.png` mostrando la regla apuntando al SG de EC2.

---

## Paso 6: Instalar Docker en EC2

Conéctate por SSH (o usa **EC2 Instance Connect** desde la consola web):

```bash
ssh -i lab-aws-key.pem ec2-user@<IP-PUBLICA-EC2>
```

Dentro de la EC2:

```bash
# Actualizar el sistema
sudo dnf update -y

# Instalar Docker y Git
sudo dnf install -y docker git unzip

# Iniciar Docker y habilitarlo en el arranque
sudo systemctl enable --now docker

# Permitir uso de Docker sin sudo
sudo usermod -aG docker ec2-user

# Aplicar el cambio de grupo en la sesión actual
newgrp docker

# Verificar
docker --version
docker ps
```

### Verificar que el IAM Role está activo

```bash
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
curl -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

Debe imprimir `EC2-AdminPanel-Role`.

---

## Paso 7: Subir el código a EC2

### Opción A — Clonar desde GitHub (recomendada, también sirve como entregable)

```bash
cd ~
git clone https://github.com/TU-USUARIO/lab-aws-flask.git
cd lab-aws-flask
```

### Opción B — Subir un ZIP por SCP

Desde **tu PC local** (PowerShell o terminal):

```bash
scp -i RUTA/lab-aws-key.pem RUTA/lab-aws-flask.zip ec2-user@IP-PUBLICA:~/
```

Luego en la EC2:

```bash
cd ~
unzip lab-aws-flask.zip
cd lab-aws-flask
```

---

## Paso 8: Configurar el archivo .env

```bash
sudo nano .env
```

> Si el archivo da error de permisos, usa `sudo` para crearlo y luego cambia el dueño:
> ```bash
> sudo chown ec2-user:ec2-user .env
> chmod 600 .env
> ```

Pega y completa con tus datos reales:

```env
SECRET_KEY=<cadena_aleatoria_larga>
ADMIN_USER=admin
ADMIN_PASSWORD=<contraseña fuerte>

DB_HOST=adminpanel-db.xxxxx.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=<contraseña de RDS>
DB_NAME=adminpanel

AWS_REGION=us-east-1
S3_BUCKET=NOMBRE-DE-TU-BUCKET
```

### Generar la `SECRET_KEY`

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copia el resultado a la variable `SECRET_KEY`.

> ⚠️ No uses comillas alrededor de los valores ni espacios alrededor del `=`. Verifica con `cat .env`.

Guardar en nano: **Ctrl + O** → Enter → **Ctrl + X**.

---

## Paso 9: Construir y arrancar el contenedor

```bash
# Construir la imagen (tarda 2-3 minutos)
docker build -t admin-panel .

# Arrancar el contenedor
docker run -d \
  --name admin-panel \
  --restart unless-stopped \
  -p 80:5000 \
  --env-file .env \
  admin-panel

# Verificar
docker ps
docker logs admin-panel
```

Los logs deben mostrar Gunicorn arrancando sin errores:
```
[INFO] Starting gunicorn 22.0.0
[INFO] Listening at: http://0.0.0.0:5000
[INFO] Booting worker with pid: 7
```

Abre en el navegador: `http://<IP-PUBLICA-EC2>` y verás la pantalla de login.

📸 **Evidencias:**
- `09_docker_ps.png`: contenedor activo.
- `10_docker_logs.png`: logs de arranque limpio.

---

## Imagen Docker en Docker Hub

La imagen del proyecto está publicada en Docker Hub, lo que permite desplegarla en cualquier servidor sin necesidad de construirla localmente.

**Repositorio:** `https://hub.docker.com/r/TU-USUARIO-DOCKERHUB/admin-panel-aws-lab`

### Despliegue rápido desde Docker Hub

En lugar de hacer `docker build` (Paso 9), puedes descargar la imagen ya construida:

```bash
# Descargar la imagen desde Docker Hub
docker pull TU-USUARIO-DOCKERHUB/admin-panel-aws-lab:latest

# Arrancar el contenedor (requiere .env configurado, ver Paso 8)
docker run -d \
  --name admin-panel \
  --restart unless-stopped \
  -p 80:5000 \
  --env-file .env \
  TU-USUARIO-DOCKERHUB/admin-panel-aws-lab:latest
```

### Cómo se publicó la imagen

```bash
# 1. Login en Docker Hub (pide usuario y contraseña/token)
docker login

# 2. Etiquetar la imagen local con el formato usuario/repo:tag
docker tag admin-panel TU-USUARIO-DOCKERHUB/admin-panel-aws-lab:latest

# 3. Subir la imagen
docker push TU-USUARIO-DOCKERHUB/admin-panel-aws-lab:latest
```

📸 **Evidencia:** `17_DockerHub_imagen.png` mostrando el repositorio en Docker Hub con la imagen publicada.

---

## Pruebas funcionales

1. **Login:** entra con las credenciales de `ADMIN_USER` / `ADMIN_PASSWORD`.
2. **Crear** un usuario llenando todos los campos y subiendo una imagen.
3. **Listar** los usuarios — la imagen debe verse correctamente.
4. **Editar** un usuario y cambiar su foto.
5. **Buscar** por nombre o email.
6. **Eliminar** un usuario (también borra la imagen de S3).
7. **Health check:** `curl http://<IP>/health` → `{"status":"ok"}`.

### Verificar la integración con AWS en tiempo real

Para mostrar en video o documentación cómo los cambios se reflejan en AWS, usa este comando en la EC2 (consulta la tabla cada 2 segundos):

```bash
watch -n 2 'docker exec admin-panel python3 -c "
from app import create_app
from app.models import User
app = create_app()
with app.app_context():
    print(f\"{\"ID\":<4} {\"Nombre\":<25} {\"Email\":<30} {\"S3 Key\":<45}\")
    print(\"-\" * 110)
    for u in User.query.all():
        print(f\"{u.id:<4} {u.full_name[:25]:<25} {u.email[:30]:<30} {(u.image_key or \"-\")[:45]}\")
"'
```

Combinado con la consola de S3 abierta en `profiles/`, se ve cómo los registros y las imágenes aparecen y desaparecen sincronizadamente.

---

## Buenas prácticas de seguridad aplicadas

- ✅ **Credenciales fuera del código:** todo en `.env`, incluido en `.gitignore`.
- ✅ **IAM Role en EC2:** la EC2 accede a S3 sin claves AWS hardcodeadas.
- ✅ **Política IAM:** acceso restringido a un bucket específico (con la Opción B).
- ✅ **Contenedor con usuario no-root:** Dockerfile crea y usa el usuario `appuser`.
- ✅ **Contraseñas hasheadas:** `pbkdf2:sha256` para el admin.
- ✅ **RDS aislada:** Security Group permite acceso solo desde el SG de la EC2.
- ✅ **Sesiones firmadas:** `SECRET_KEY` aleatoria de 64 caracteres.
- ✅ **Validación de archivos:** solo extensiones de imagen (`png/jpg/jpeg/gif/webp`), tope de 5 MB.
- ✅ **Cifrado en reposo:** RDS y S3 cifrados por defecto.
- ✅ **SSH restringido:** acceso solo desde la IP del administrador.
- ✅ **Decorador `@login_required`** en todas las rutas CRUD.
- ✅ **Permisos restrictivos del `.env`:** `chmod 600` (solo lectura del propietario).

---

## Evidencias requeridas (checklist del entregable)

### AWS - Infraestructura
- [ ] `01_S3_bucket_creado.png` — bucket creado en la lista.
- [ ] `02_S3_policy.png` — política JSON aplicada al bucket.
- [ ] `03_S3_objetos.png` — carpeta `profiles/` con imágenes subidas.
- [ ] `04_RDS_disponible.png` — instancia con estado "Disponible" y endpoint visible.
- [ ] `05_IAM_role.png` — rol con política S3 adjunta.
- [ ] `06_EC2_instancia.png` — instancia en ejecución con IP pública.
- [ ] `07_SG_RDS.png` — regla MySQL 3306 desde el SG de EC2.
- [ ] `08_SG_EC2.png` — reglas SSH (22) y HTTP (80).

### Docker en EC2
- [ ] `09_docker_ps.png` — contenedor activo.
- [ ] `10_docker_logs.png` — logs de Gunicorn sin errores.

### App funcionando
- [ ] `11_app_login.png` — pantalla de login.
- [ ] `12_app_lista_usuarios.png` — lista con varios usuarios y fotos.
- [ ] `13_app_crear_usuario.png` — formulario de creación.
- [ ] `14_app_editar_usuario.png` — formulario de edición con datos pre-cargados.
- [ ] `15_app_eliminar.png` — confirmación de eliminación.

### Base de datos
- [ ] `16_DB_query_users.png` — consulta a la tabla `users` mostrando registros.

### Docker Hub
- [ ] `17_DockerHub_imagen.png` — repositorio en Docker Hub con la imagen publicada.

### Entregables finales
- [ ] URL del **repositorio Git público** (GitHub).
- [ ] URL del **repositorio Docker Hub**.
- [ ] **Video de demostración** mostrando CRUD reflejándose en AWS en tiempo real.
- [ ] Este **README.md** como documentación técnica.

---

## Troubleshooting

| Problema | Solución |
|---|---|
| `Can't connect to MySQL server` | Verifica que el SG de RDS permita conexión desde el SG de EC2 en puerto 3306, y que RDS esté en estado "Disponible". |
| `Access denied for user` | Contraseña de RDS mal escrita en `.env`. Edita y reinicia el contenedor. |
| `Unknown database 'adminpanel'` | No pusiste "Nombre de base de datos inicial" al crear RDS. Conéctate por CLI desde la EC2 y créala: `CREATE DATABASE adminpanel;`. |
| `NoCredentialsError` al subir a S3 | Rol IAM no adjunto a la EC2. Verifica con el comando IMDSv2 del Paso 6. |
| Imágenes no se ven en el navegador | Falta política pública del bucket (Paso 1) o "Bloquear acceso público" sigue activado. |
| `Permission denied` al editar `.env` | Usa `sudo nano .env` y luego `sudo chown ec2-user:ec2-user .env`. |
| `Port 80 already in use` | `sudo lsof -i :80` y mata el proceso, o cambia el mapeo en `docker run -p 8080:5000`. |
| Cambios en código no se reflejan | Reconstruye: `docker stop admin-panel && docker rm admin-panel && docker build -t admin-panel . && docker run -d --name admin-panel -p 80:5000 --env-file .env admin-panel`. |
| `Connection timed out` al hacer SSH | Tu IP pública cambió. Edita el SG de EC2 y actualiza la regla SSH con tu IP actual ("Mi IP"). |
| Build de Docker muy lento | Verifica que la EC2 sea al menos t2.micro/t3.micro y tenga conexión a internet (la VPC default trae internet gateway). |

---

## Comandos útiles

```bash
# Ver logs en vivo
docker logs -f admin-panel

# Reiniciar el contenedor
docker restart admin-panel

# Entrar al contenedor para inspeccionar
docker exec -it admin-panel bash

# Consultar la tabla users desde fuera del contenedor
docker exec -it admin-panel python3 -c "
from app import create_app
from app.models import User
app = create_app()
with app.app_context():
    for u in User.query.all():
        print(u.id, u.full_name, u.email, u.image_url)
"

# Actualizar desde GitHub
cd ~/lab-aws-flask
git pull
docker stop admin-panel && docker rm admin-panel
docker build -t admin-panel .
docker run -d --name admin-panel --restart unless-stopped -p 80:5000 --env-file .env admin-panel
```

---

## Limpiar recursos

Para evitar cargos después de entregar el laboratorio:

1. **EC2:** Acciones → Estado de instancia → **Terminar instancia**.
2. **RDS:** Acciones → **Eliminar** → desmarca "Crear snapshot final" → escribe el texto de confirmación.
3. **S3:** **Vaciar** el bucket → luego **Eliminar bucket**.
4. **IAM Role:** opcional (no cuesta, pero puedes eliminarlo).
5. **Security Groups y Key Pairs:** opcionales (gratis).

---

## Autor

Laboratorio de Computación en la Nube — 2026.