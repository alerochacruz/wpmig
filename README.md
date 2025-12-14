# WPMIG: Migrador de WordPress

**WPMIG** es una herramienta de línea de comandos en Python diseñada para facilitar la migración de sitios WordPress entre servidores Linux.

El proceso, que normalmente requiere múltiples pasos manuales y es propenso a errores, aquí se convierte en un flujo **guiado, seguro y reproducible**, donde los parámetros pueden ingresarse de forma interactiva o precargarse en un archivo `.env` para agilizar la confirmación.

## Características principales

- Migración integral de **base de datos** y **sistema de archivos**.  
- Validación previa del entorno (SSH, stack LAMP, credenciales, espacio en disco).  
- Ejecución de **tareas post‑migración** para asegurar la operatividad del sitio.  
- Registro detallado en `wp_migration.log` para trazabilidad y auditoría.  
- Arquitectura modular y extensible, basada en componentes independientes.  

## Estructura del proyecto

```text
wpmig/
├── config.py
├── database.py
├── demo_keys
│   ├── demo_ed25519
│   ├── demo_ed25519.pub
│   └── generate_ssh_keys.sh
├── .env_demo
├── filesystem.py
├── .gitignore
├── install_lamp.sh
├── install_wordpress.sh
├── main.py
├── postmigration.py
├── requirements.txt
├── Vagrantfile
└── validation.py
```

## Instalación

1. Clonar el repositorio que contiene la aplicación.
2. Crea un entorno virtual para instalar las dependencias sin afectar el sistema:
    ```text
    python -m venv .venv
    source .venv/bin/activate   # En Linux / macOS
    .venv\Scripts\activate      # En Windows
    ```
3. Instalar las dependencias:
    ```text
    pip install -r requirements.txt
    ```
> **Nota:** Para desactivar el entorno virtual cuando termines de usar la aplicación, simplemente ejecuta:
>
> ```text
> deactivate
> ```

## Uso de la aplicación

La herramienta puede ejecutarse de dos formas:

1. **Modo interactivo**  
   Si no existe un archivo `.env` o faltan variables, la aplicación solicitará todos los parámetros paso a paso (host, usuario, método de autenticación, rutas de WordPress, URLs, etc.).  
   ```text
   python main.py
   ```

2. **Modo con `.env` (interactivo asistido)**  
   Si se define un archivo `.env` en la raíz del proyecto, la aplicación precargará los valores allí configurados.  
   Durante la ejecución, cada parámetro se mostrará en pantalla y el usuario deberá confirmarlo presionando *Enter* o modificarlo en el momento.  
   ```text
   cp .env_demo .env
   python main.py
   ```

En ambos casos, **WPMIG** guía el flujo completo de migración: validación del entorno, transferencia de base de datos y archivos, tareas post‑migración y registro en `wp_migration.log`.

## Demostración en video

[![Ver video](https://i.postimg.cc/XqLVPJZL/Screenshot-From-2025-12-14-18-47-18.png)](https://vimeo.com/1146404661)

## Entorno de pruebas con Vagrant (opcional)

El proyecto incluye un `Vagrantfile` que permite levantar un entorno de pruebas reproducible con **dos servidores Debian 12 (Bookworm)**. Este entorno está pensado para validar el funcionamiento de **WPMIG** sin necesidad de usar servidores de producción.

### Detalles del entorno

- **Servidor de origen – genesis**
  - Hostname: `server-01-genesis`
  - IP: `192.168.0.250`
  - Recursos: 2 vCPUs, 2 GB RAM
  - Provisionado con **WordPress** mediante `install_wordpress.sh`
  - Autenticación SSH habilitada para usuarios `root` y `vagrant` (contraseña: `vagrant` + llaves en `demo_keys/`)

- **Servidor de destino – exodus**
  - Hostname: `server-02-exodus`
  - IP: `192.168.0.251`
  - Recursos: 2 vCPUs, 2 GB RAM
  - Provisionado con **stack LAMP** mediante `install_lamp.sh`
  - Autenticación SSH habilitada para usuarios `root` y `vagrant` (contraseña: `vagrant` + llaves en `demo_keys/`)

> **Importante:** Ambos servidores están configurados en **red pública (bridge)**. Es necesario ajusta la interfaz (`wlo1`) y las direcciones IP según el sistema anfitrión antes de levantar el entorno.

### Levantar el entorno

```text
# Desde la raíz del proyecto
vagrant up
```

### Acceso vía SSH

**Con contraseña (usuario root):**

```text
ssh root@192.168.0.250   # Servidor de origen
ssh root@192.168.0.251   # Servidor de destino
```

**Con llaves (usuario root):**

```text
ssh -i ./demo_keys/demo_ed25519 root@192.168.0.250   # Servidor de origen
ssh -i ./demo_keys/demo_ed25519 root@192.168.0.251   # Servidor de destino
```

**Mediante Vagrant:**

```text
vagrant ssh genesis   # Servidor de origen
vagrant ssh exodus    # Servidor de destino
```

### Destruir el entorno

```text
vagrant destroy -f
```

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Puedes usar, copiar, modificar y distribuir el software, siempre que mantengas el aviso de copyright y esta licencia.
