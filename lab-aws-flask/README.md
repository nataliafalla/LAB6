# Admin Panel - Laboratorio AWS (Flask + RDS MySQL + S3 + Docker + EC2)

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
9. [Paso 5: Instalar Docker en EC2](#paso-5-instalar-docker-en-ec2)
10. [Paso 6: Desplegar la aplicación](#paso-6-desplegar-la-aplicación)
11. [Pruebas](#pruebas)
12. [Buenas prácticas de seguridad](#buenas-prácticas-de-seguridad)
13. [Evidencias requeridas](#evidencias-requeridas)
14. [Troubleshooting](#troubleshooting)

---

## Arquitectura

```
                    ┌──────────────────┐
                    │   Navegador      │
                    │   (Admin)        │
                    └────────┬─────────┘
                             │ HTTP/HTTPS
                             ▼
        ┌────────────────────────────────────────┐
        │   EC2 (Amazon Linux 2023)              │
        │   ┌──────────────────────────────┐     │
        │   │  Docker Container            │     │
        │   │  Flask + Gunicorn :5000      │     │
        │   └──────────────────────────────┘     │
        │   IAM Role: S3FullAccess (limitado)    │
        └──────┬──────────────────────┬──────────┘
               │                      │
               ▼                      ▼
        ┌──────────────┐      ┌──────────────┐
        │  RDS MySQL   │      │   S3 Bucket  │
        │  (privada)   │      │  (imágenes)  │
        └──────────────┘      └──────────────┘
```

## Stack

- **Backend:** Python 3.12, Flask 3, SQLAlchemy, Flask-Login
- **Servidor:** Gunicorn (3 workers)
- **Base de datos:** Amazon RDS MySQL 8
- **Storage:** Amazon S3
- **Contenedor:** Docker
- **Host:** EC2 (Amazon Linux 2023, t3.micro)

## Estructura del proyecto

```
lab-aws-flask/
├── app/
│   ├── __init__.py          # Factory de Flask, config DB
│   ├── auth.py              # Login/logout admin
│   ├── routes.py            # CRUD de usuarios
│   ├── models.py            # Admin, User
│   ├── s3_utils.py          # Subir/borrar imágenes en S3
│   ├── templates/           # HTML (Jinja2)
│   └── static/style.css
├── run.py                   # Entrypoint
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Prerrequisitos

- Cuenta AWS activa
- AWS CLI configurada (opcional, recomendado)
- Par de llaves SSH (.pem) creado en EC2 → Key Pairs
- Git instalado localmente

---

## Paso 1: Crear bucket S3

1. Consola AWS → **S3** → **Create bucket**
2. Nombre único: `mi-bucket-perfiles-lab-<tu-nombre>`
3. Región: `us-east-1` (o la que prefieras, anótala)
4. **Block all public access**: déjalo activado (más seguro).
5. Crear el bucket.
6. (Opcional) Si quieres que las imágenes se muestren directamente vía URL pública, desbloquea el acceso público y agrega esta **Bucket Policy**:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadProfiles",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::mi-bucket-perfiles-lab-<tu-nombre>/profiles/*"
  }]
}
```

**CORS** (Permissions → CORS):

```json
[{
  "AllowedHeaders": ["*"],
  "AllowedMethods": ["GET", "PUT", "POST"],
  "AllowedOrigins": ["*"],
  "ExposeHeaders": []
}]
```

📸 **Evidencia:** captura del bucket creado y de la política.

---

## Paso 2: Crear base de datos RDS MySQL

1. Consola AWS → **RDS** → **Create database**
2. Engine: **MySQL** 8.0
3. Template: **Free tier**
4. DB instance identifier: `adminpanel-db`
5. Master username: `admin`
6. Master password: anótala (será `DB_PASSWORD`)
7. Instance class: `db.t3.micro`
8. Storage: 20 GB GP2
9. **Connectivity:**
   - VPC: la default
   - Public access: **No** (más seguro). Si quieres conectarte desde tu PC para inspeccionar, ponlo en **Yes** solo durante el lab.
   - VPC security group: crea uno nuevo `rds-sg`
10. Database authentication: Password authentication
11. **Additional configuration → Initial database name:** `adminpanel`
12. Crear.

**Configurar el Security Group de RDS:**

- Después de creado, edita `rds-sg`.
- Inbound rule: **MySQL/Aurora (3306)**, source = el Security Group de la EC2 (lo crearás en el paso 4). Por ahora puedes dejar `0.0.0.0/0` temporalmente y luego restringirlo.

📸 **Evidencia:** captura del endpoint de RDS (lo verás como `adminpanel-db.xxxxx.us-east-1.rds.amazonaws.com`).

---

## Paso 3: Crear IAM Role para EC2

Esto evita poner credenciales AWS dentro del contenedor.

1. Consola AWS → **IAM** → **Roles** → **Create role**
2. Trusted entity: **AWS service** → **EC2**
3. Permissions: agrega política inline (más segura que `AmazonS3FullAccess`):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ],
    "Resource": [
      "arn:aws:s3:::mi-bucket-perfiles-lab-<tu-nombre>",
      "arn:aws:s3:::mi-bucket-perfiles-lab-<tu-nombre>/*"
    ]
  }]
}
```

4. Nombre del rol: `EC2-AdminPanel-Role`

📸 **Evidencia:** captura del rol creado y la política.

---

## Paso 4: Lanzar instancia EC2

1. Consola AWS → **EC2** → **Launch instance**
2. Nombre: `admin-panel-server`
3. AMI: **Amazon Linux 2023**
4. Tipo: `t3.micro` (free tier)
5. Key pair: selecciona la tuya
6. **Network settings:**
   - Crear Security Group `ec2-sg` con reglas:
     - SSH (22) desde **tu IP**
     - HTTP (80) desde `0.0.0.0/0`
     - (Opcional) HTTPS (443) desde `0.0.0.0/0`
7. **Advanced details → IAM instance profile:** selecciona `EC2-AdminPanel-Role`
8. Launch.

**Actualiza el SG de RDS:** quita `0.0.0.0/0` del puerto 3306 y deja solo el SG `ec2-sg` como source.

📸 **Evidencia:** captura de la instancia EC2 con IP pública.

---

## Paso 5: Instalar Docker en EC2

Conéctate por SSH:

```bash
ssh -i tu-llave.pem ec2-user@<IP-PUBLICA-EC2>
```

Instala Docker:

```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
# Cierra y vuelve a abrir SSH para aplicar el grupo
exit
```

Vuelve a entrar y verifica:

```bash
docker --version
docker ps
```

---

## Paso 6: Desplegar la aplicación

En la EC2:

```bash
git clone https://github.com/<tu-usuario>/lab-aws-flask.git
cd lab-aws-flask
cp .env.example .env
nano .env
```

Edita `.env` con tus valores reales:

```
SECRET_KEY=<genera con: python3 -c "import secrets; print(secrets.token_hex(32))">
ADMIN_USER=admin
ADMIN_PASSWORD=<contraseña fuerte>
DB_HOST=adminpanel-db.xxxxx.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=<password de RDS>
DB_NAME=adminpanel
AWS_REGION=us-east-1
S3_BUCKET=mi-bucket-perfiles-lab-<tu-nombre>
```

**Construir y correr el contenedor:**

```bash
docker build -t admin-panel .
docker run -d \
  --name admin-panel \
  --restart unless-stopped \
  -p 80:5000 \
  --env-file .env \
  admin-panel
```

Verifica:

```bash
docker ps
docker logs admin-panel
curl http://localhost/health
```

Abre el navegador en `http://<IP-PUBLICA-EC2>` y entra con las credenciales de `.env`.

📸 **Evidencia:** captura del contenedor corriendo (`docker ps`) y de la app funcionando en el navegador.

---

## Pruebas

1. **Login:** entra con `admin` / contraseña.
2. **Crear:** click en "+ Nuevo usuario", llena el formulario, sube una imagen.
3. **Listar:** verifica que aparezca en la tabla con su foto.
4. **Editar:** modifica datos o cambia la imagen.
5. **Eliminar:** confirma eliminación (también borra la imagen de S3).
6. **Health check:** `curl http://<IP>/health` → `{"status":"ok"}`.

**Verificar S3:** en la consola entra al bucket, en `profiles/` deberías ver las imágenes subidas.

**Verificar RDS:** desde la EC2:

```bash
docker exec -it admin-panel python -c "from app import create_app, db; from app.models import User; app=create_app(); ctx=app.app_context(); ctx.push(); print(User.query.all())"
```

📸 **Evidencias:** capturas de S3 con los archivos y de la tabla `users` en RDS (puedes usar MySQL Workbench si habilitaste acceso público temporalmente).

---

## Buenas prácticas de seguridad aplicadas

- ✅ **Credenciales fuera del código:** todo en `.env` (incluido en `.gitignore`).
- ✅ **IAM Role en EC2:** sin claves AWS hardcodeadas en el contenedor.
- ✅ **Política IAM mínima:** solo `s3:GetObject/PutObject/DeleteObject` sobre el bucket específico.
- ✅ **Usuario no-root en Docker:** el contenedor corre como `appuser`.
- ✅ **Passwords hasheados:** Werkzeug `pbkdf2:sha256` para el admin.
- ✅ **RDS privada:** Security Group permite acceso solo desde el SG de la EC2.
- ✅ **Sesiones firmadas:** `SECRET_KEY` aleatorio.
- ✅ **Validación de archivos:** solo imágenes (`png/jpg/jpeg/gif/webp`), máx 5MB.
- ✅ **CSRF implícito:** formularios `same-origin`. (Si quieres reforzar, instala Flask-WTF y activa `CSRFProtect`).
- ✅ **`@login_required` en todas las rutas CRUD.**

---

## Evidencias requeridas (checklist para el entregable)

- [ ] Captura del **bucket S3** creado, con objetos en `profiles/`.
- [ ] Captura de la **instancia RDS** mostrando el endpoint.
- [ ] Captura del **IAM Role** y su política asociada.
- [ ] Captura de la **instancia EC2** corriendo con IP pública.
- [ ] Captura del **Security Group** de EC2 y de RDS.
- [ ] Captura de `docker ps` mostrando el contenedor activo.
- [ ] Captura de `docker logs admin-panel` mostrando arranque exitoso.
- [ ] Capturas del **login**, **lista de usuarios**, **crear/editar/eliminar** funcionando.
- [ ] Captura de la **tabla `users`** en la base de datos.
- [ ] URL del **repositorio Git** (público).
- [ ] Este README como **documentación técnica**.

---

## Troubleshooting

| Problema | Solución |
|---|---|
| `Can't connect to MySQL server` | Revisa que el SG de RDS permita el SG de EC2 en puerto 3306. |
| `An error occurred (AccessDenied) when calling the PutObject` | El IAM Role no está adjunto a la EC2 o le falta permiso S3. Verifica con `aws sts get-caller-identity` dentro de la EC2. |
| Las imágenes no se ven en el navegador | El bucket es privado. Aplica la Bucket Policy de lectura pública para `profiles/*` o usa `generate_presigned_url`. |
| `Port 80 already in use` | `sudo lsof -i :80` y mata el proceso, o cambia el mapeo en `docker run`. |
| Cambios en código no se reflejan | `docker stop admin-panel && docker rm admin-panel && docker build -t admin-panel . && docker run -d ...` |

---

## Comandos útiles

```bash
# Ver logs en vivo
docker logs -f admin-panel

# Reiniciar
docker restart admin-panel

# Entrar al contenedor
docker exec -it admin-panel bash

# Actualizar desde Git
git pull
docker build -t admin-panel .
docker stop admin-panel && docker rm admin-panel
docker run -d --name admin-panel --restart unless-stopped -p 80:5000 --env-file .env admin-panel
```

---

## Autor

Laboratorio de Computación en la Nube — 2026.
