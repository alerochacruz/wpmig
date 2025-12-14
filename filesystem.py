"""
Módulo de migración del sistema de archivos para migraciones de sitios WordPress.

Este módulo gestiona la transferencia de los archivos de WordPress desde el
servidor de origen al de destino. Crea copias de seguridad, prepara directorios,
transfiere archivos usando tar y SFTP, y establece los permisos de archivo adecuados.

Funciones:
    get_wordpress_path: Encuentra la ruta de instalación de WordPress.
    calculate_directory_size: Calcula el tamaño total del directorio de WordPress.
    create_backup_on_destination: Realiza una copia de seguridad del WordPress existente en el destino.
    prepare_destination_directory: Limpia y prepara el directorio de destino.
    transfer_files_with_tar: Transfiere archivos usando un archivo tar a través de SFTP.
    set_file_permissions: Establece los permisos correctos de archivos para WordPress.
    run_filesystem_migration: Ejecuta el flujo completo de migración del sistema de archivos.

Ejemplo:
    from filesystem import run_filesystem_migration
    
    success = run_filesystem_migration(
        source_ssh=source_ssh,
        dest_ssh=dest_ssh,
        source_config=source_config,
        dest_config=dest_config,
        create_backup=True
    )
"""

import paramiko
import logging
import sys
import time
import os
from dotenv import load_dotenv
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('wp_migration.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def execute_remote_command(ssh_client: paramiko.SSHClient, 
                           command: str) -> tuple:
    """
    Ejecuta comando en servidor remoto vía SSH.
    
    Args:
        ssh_client: Cliente SSH conectado.
        command: Comando a ejecutar.
    
    Returns:
        Tupla con (exit_code, stdout, stderr).
    """
    stdin, stdout, stderr = ssh_client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, stdout.read().decode().strip(), stderr.read().decode().strip()


def get_wordpress_path(ssh_client: paramiko.SSHClient) -> str:
    """
    Encuentra ruta de instalación de WordPRess en servidor.

    Esta función es aplicable tanto para el servidor de origen como para
    el de destino. Revisa una lista predefinida de directorios de instalación
    comunes de WordPress y devuelve el primero que contiene un
    archivo wp-config.php válido.
    
    Args:
        ssh_client: Cliente SSH conectado.
    
    Returns:
        Ruta de instalación de WordPress o cadena vacía si no se encuentra.
    """
    wp_paths = ['/var/www/html', '/var/www/wordpress', '/usr/share/nginx/html']
    
    for path in wp_paths:
        exit_code, _, _ = execute_remote_command(
            ssh_client, 
            f"test -f {path}/wp-config.php && echo 'found'"
        )
        if exit_code == 0:
            return path
    
    return ""


def calculate_directory_size(ssh_client: paramiko.SSHClient, 
                             path: str) -> tuple:
    """
    Calcula el tamaño total de un directorio.
    
    Args:
        ssh_client: Cliente SSH conectado.
        path: Ruta de directorio.
    
    Returns:
        Tupla con (success, size_in_mb, size_human_readable).
    """
    # Obtener tamaño en MB
    exit_code, size_mb, _ = execute_remote_command(
        ssh_client,
        f"du -sm {path} | awk '{{print $1}}'"
    )
    
    if exit_code != 0:
        return False, 0, ""
    
    # Obtener tamaño legible para humanos
    exit_code, size_human, _ = execute_remote_command(
        ssh_client,
        f"du -sh {path} | awk '{{print $1}}'"
    )
    
    return True, int(size_mb), size_human


def create_backup_on_destination(dest_ssh: paramiko.SSHClient,
                                 dest_wp_path: str) -> tuple:
    """
    Crea un backup de una instalación existente de WordPress en destino.
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        dest_wp_path: Ruta de WordPress en destino.
    
    Returns:
        Tupla con (success, message, backup_path).
    """
    logger.info("=" * 60)
    logger.info("Creando backup en destino")
    logger.info("=" * 60)
    
    # Verificar si WordPress existe en destino
    exit_code, _, _ = execute_remote_command(
        dest_ssh,
        f"test -d {dest_wp_path} && echo 'exists'"
    )
    
    if exit_code != 0:
        logger.info(":!: No se encontró ninguna instalación existende de WordPress en destino")
        logger.info("   Omitiendo paso de backup")
        return True, "No es necesario ningún backup", ""
    
    # Crear un backup con timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"/tmp/wp_backup_{timestamp}"
    
    logger.info(f"Realizando backup de WorPress existente a: {backup_path}")
    
    # Copiar WordPress existente a la ubicación de backup
    exit_code, _, stderr = execute_remote_command(
        dest_ssh,
        f"cp -r {dest_wp_path} {backup_path}"
    )
    
    if exit_code != 0:
        return False, f"Error al realizar backup: {stderr}", ""
    
    logger.info(f":✓: Backup creado con éxito en {backup_path}")
    return True, "Backup creado", backup_path


def prepare_destination_directory(dest_ssh: paramiko.SSHClient,
                                  dest_wp_path: str) -> tuple:
    """
    Prepara directorio de destino para instalación de WordPress.
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        dest_wp_path: Ruta de WordPress en destino.
    
    Returns:
        Tupla con (success, message).
    """
    logger.info("=" * 60)
    logger.info("Preparando directorio de destino")
    logger.info("=" * 60)
    
    logger.info(f"Ruta de destino: {dest_wp_path}")
    
    # Verificar si un directorio existe y elimina contenidos
    exit_code, _, _ = execute_remote_command(
        dest_ssh,
        f"test -d {dest_wp_path} && echo 'exists'"
    )
    
    if exit_code == 0:
        logger.info("Eliminando archivos existentes de WordPress...")
        exit_code, _, stderr = execute_remote_command(
            dest_ssh,
            f"rm -rf {dest_wp_path}/*"
        )
        
        if exit_code != 0:
            return False, f"Error al limpiar el directorio de destino: {stderr}"
        
        logger.info(":✓: Archivos existentes elminados")
    else:
        # Crear directorio si no existe
        logger.info("Creando directorio de destino...")
        exit_code, _, stderr = execute_remote_command(
            dest_ssh,
            f"sudo mkdir -p {dest_wp_path}"
        )
        
        if exit_code != 0:
            return False, f"Error al crear directorio de destino: {stderr}"
        
        logger.info(":✓: Directorio creado")
    
    return True, "Directorio de destino preparado"


def transfer_files_with_tar(source_ssh: paramiko.SSHClient,
                            dest_ssh: paramiko.SSHClient,
                            source_wp_path: str,
                            dest_wp_path: str) -> tuple:
    """
    Transfiere archivos utilizando tar + SFTP.
    
    Args:
        source_ssh: Cliente SSH conectado a origen.
        dest_ssh: Cliente SSH conectado a destino.
        source_wp_path: Ruta de WordPress en origen.
        dest_wp_path: Ruta de WordPress en destino.
    
    Returns:
        Tupla con (success, message).
    """
    logger.info("=" * 60)
    logger.info("Transfiriendo archivos de WordPress")
    logger.info("=" * 60)
    
    # Obtener tamaño de directorio de origen
    success, size_mb, size_human = calculate_directory_size(source_ssh, source_wp_path)
    if success:
        logger.info(f"Tamaño del directorio de origen: {size_human} ({size_mb} MB)")
    
    logger.info(f"Directorio de origen: {source_wp_path}")
    logger.info(f"Directorio de destino: {dest_wp_path}")
    logger.info("\nMétodo de transferencia: tar + SFTP")
    
    # Crear archivo tar temporal
    temp_tar = "/tmp/wordpress_files.tar.gz"
    
    logger.info("\nCreando archivo en servidor origen...")
    logger.info("  (Esto puede tomar un tiempo dependiendo del tamaño del sitio)")
    
    start_time = time.time()
    tar_cmd = f"cd {source_wp_path} && tar -czf {temp_tar} ."
    exit_code, _, stderr = execute_remote_command(source_ssh, tar_cmd)
    
    if exit_code != 0:
        return False, f"Error al crear archivo: {stderr}"
    
    # Obtener tamaño de archivo
    exit_code, archive_size, _ = execute_remote_command(
        source_ssh,
        f"du -h {temp_tar} | cut -f1"
    )
    
    elapsed = time.time() - start_time
    logger.info(f":✓: Archivo creado en {int(elapsed)}s (tamaño: {archive_size})")
    
    # Transferir archivo utilizando SFTP
    logger.info("\nTransfiriendo archivo a destino...")
    logger.info("  (Este es el paso más largo - por favor sea paciente)")
    
    try:
        source_sftp = source_ssh.open_sftp()
        dest_sftp = dest_ssh.open_sftp()
        
        # Descargar desde origen a archivo local temporal
        local_temp = "/tmp/wordpress_transfer.tar.gz"
        
        logger.info("  - Descargando desde servidor origen...")
        transfer_start = time.time()
        source_sftp.get(temp_tar, local_temp)
        
        download_time = time.time() - transfer_start
        logger.info(f"    Descargando en {int(download_time)}s")
        
        # Subir a destino
        logger.info("  - Subiendo al servidor destino...")
        upload_start = time.time()
        dest_sftp.put(local_temp, temp_tar)
        
        upload_time = time.time() - upload_start
        logger.info(f"    Subido en {int(upload_time)}s")
        
        source_sftp.close()
        dest_sftp.close()
        
        # Eliminar archivo local temporal
        os.remove(local_temp)
        
        total_transfer_time = time.time() - transfer_start
        logger.info(f":✓: Transferencia completeada en {int(total_transfer_time)}s")
        
    except Exception as e:
        return False, f"Error al transferir archivo: {str(e)}"
    
    # Extraer en destino
    logger.info("\nExtrayendo archivos en server destino...")
    extract_start = time.time()
    
    extract_cmd = f"cd {dest_wp_path} && tar -xzf {temp_tar}"
    exit_code, _, stderr = execute_remote_command(dest_ssh, extract_cmd)
    
    if exit_code != 0:
        return False, f"Error al extraer archivo: {stderr}"
    
    extract_time = time.time() - extract_start
    logger.info(f":✓: Archivos extraídos en {int(extract_time)}s")
    
    # Verificar extracción
    logger.info("\nValidando archivos transferidos...")
    exit_code, file_count, _ = execute_remote_command(
        dest_ssh,
        f"find {dest_wp_path} -type f | wc -l"
    )
    
    if exit_code == 0 and int(file_count) > 0:
        logger.info(f":✓: Validados {file_count} archivos en destino")
    else:
        logger.warning(":!: No se pudo validar conteo de archivos")
    
    # Eliminar archivos tar
    logger.info("\nLimpiando archivos temporales...")
    execute_remote_command(source_ssh, f"rm -f {temp_tar}")
    execute_remote_command(dest_ssh, f"rm -f {temp_tar}")
    logger.info(":✓: Limpieza completa")
    
    total_time = time.time() - start_time
    minutes = int(total_time // 60)
    seconds = int(total_time % 60)
    
    return True, f"Archivos transferidos con éxito en {minutes}m {seconds}s ({size_human})"


def set_file_permissions(dest_ssh: paramiko.SSHClient,
                        dest_wp_path: str,
                        web_user: str = "www-data") -> tuple:
    """
    Establecer permisos de archivo correctos para WordPress.
    Las variable de entoro WEB_USER puede sobreescribir el valor
    predeterminado del usuario del servidor web.
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        dest_wp_path: Ruta de WordPress en destino.
        web_user: Usuario del servidor web (predeterminado: www-data).
    
    Returns:
        Tupla con (success, message).
    """
    # Permitir sobreescritura desde .env
    env_web_user = os.getenv("WEB_USER")
    if env_web_user:
        web_user = env_web_user

    logger.info("=" * 60)
    logger.info("Estableciendo permisos de archivos")
    logger.info("=" * 60)
    
    logger.info(f"Ruta de WordPress: {dest_wp_path}")
    logger.info(f"Usuario web server: {web_user}")
    
    # Establecer propiedad
    logger.info("\nEstableciendo propiedad de archivos...")
    chown_cmd = f"sudo chown -R {web_user}:{web_user} {dest_wp_path}"
    exit_code, _, stderr = execute_remote_command(dest_ssh, chown_cmd)
    
    if exit_code != 0:
        logger.warning(f":!: No se pudo establecer propiedad: {stderr}")
        logger.warning("   Es posible que necesite establecer propiedad manualmente con sudo")
    else:
        logger.info(f":✓: Propiedad establecida a {web_user}:{web_user}")
    
    # Establecer permisos de directorio (755)
    logger.info("\nEstableciendo permisos de directorio (755)...")
    dir_perm_cmd = f"find {dest_wp_path} -type d -exec chmod 755 {{}} \\;"
    exit_code, _, stderr = execute_remote_command(dest_ssh, dir_perm_cmd)
    
    if exit_code != 0:
        return False, f"Failed to set directory permissions: {stderr}"
        return False, f"Error al establecer permisos de directorio: {stderr}"
    
    logger.info(":✓: Permisos de directorio establecidos")
    
    # Establecer permisos de archivo (644)
    logger.info("\nSetting file permissions (644)...")
    logger.info("\nEstableciendo permisos de archivo (644)...")
    file_perm_cmd = f"find {dest_wp_path} -type f -exec chmod 644 {{}} \\;"
    exit_code, _, stderr = execute_remote_command(dest_ssh, file_perm_cmd)
    
    if exit_code != 0:
        return False, f"Error al establecer permisos de archivo: {stderr}"
    
    logger.info(":✓: Permisos de archivo establecidos")
    
    # Asegurar wp-config.php
    logger.info("\nAsegurando wp-config.php (640)...")
    exit_code, _, _ = execute_remote_command(
        dest_ssh,
        f"chmod 640 {dest_wp_path}/wp-config.php"
    )
    
    if exit_code == 0:
        logger.info(":✓: wp-config.php asegurado")
    
    return True, "Permisos de archivo establecidos correctamente"


def run_filesystem_migration(source_ssh: paramiko.SSHClient,
                             dest_ssh: paramiko.SSHClient,
                             source_config: dict,
                             dest_config: dict,
                             create_backup: bool = True) -> bool:
    """
    Flujo completo de migración del sistema de archivos.
    Las variables de entorno SOURCE_WP_PATH, DESTINATION_WP_PATH y DESTINATION_WEB_USER
    pueden utilizarse para proporcionar valores predeterminados para la ruta de WordPress
    de origen, la ruta de WordPress de destino y el usuario del servidor web de destino.

    Args:
        source_ssh: Cliente SSH conectado a origen.
        dest_ssh: Cliente SSH conectado a destino.
        source_config: Diccionario con la configuración del servidor origen.
        dest_config: Diccionario con la configuración del servidor destino.
        create_backup: Indica si se debe crear un backup de los archivos existentes en destino.

    Returns:
        Booleano. True si la migración se completa correctamente, False en caso contrario.
    """
    try:
        # Paso 1: Localizar rutas de WordPress
        logger.info("Localizando instalaciones de WordPress...")

        # Cargar sobreescritura opcional para ruta de origen
        env_src_wp_path = os.getenv("SOURCE_WP_PATH")

        if env_src_wp_path:
            # Validar sobreescritura
            exit_code, _, _ = execute_remote_command(
                source_ssh,
                f"test -f {env_src_wp_path}/wp-config.php && echo 'found'"
            )
            if exit_code == 0:
                source_wp_path = env_src_wp_path
            else:
                logger.warning(f":!: SOURCE_WP_PATH provisto pero wp-config.php no encontrado en {env_src_wp_path}")
                source_wp_path = get_wordpress_path(source_ssh)
        else:
            source_wp_path = get_wordpress_path(source_ssh)

        if not source_wp_path:
            logger.error(":x: WordPress no encontrado en servidor origen")
            return False

        # Ruta de sobreescritura de destino
        env_dest_wp_path = os.getenv("DESTINATION_WP_PATH", source_wp_path)

        dest_wp_path = input(
            f"\nRuta de destino de WordPress [{env_dest_wp_path}]: "
        ).strip() or env_dest_wp_path

        logger.info(f"WordPress origen: {source_wp_path}")
        logger.info(f"WordPress destino: {dest_wp_path}")
        
        # Paso 2: Crear backup en destino (opcional)
        if create_backup:
            success, message, backup_path = create_backup_on_destination(
                dest_ssh, dest_wp_path
            )
            if not success:
                logger.error(f":x: {message}")
                return False
        
        # Paso 3: Preparar directorio de destino
        success, message = prepare_destination_directory(dest_ssh, dest_wp_path)
        if not success:
            logger.error(f":x: {message}")
            return False
        
        # Paso 4: Transferir archivos usando tar + SFTP
        success, message = transfer_files_with_tar(
            source_ssh, dest_ssh,
            source_wp_path, dest_wp_path
        )
        if not success:
            logger.error(f":x: {message}")
            return False
        
        logger.info(f"\n:✓: {message}")
        
        # Paso 5: Establecer permisos correctos
        env_dest_web_user = os.getenv("DESTINATION_WEB_USER", "www-data")

        web_user = input(
            f"\nUsuario web server [{env_dest_web_user}]: "
        ).strip() or env_dest_web_user

        success, message = set_file_permissions(dest_ssh, dest_wp_path, web_user)
        if not success:
            logger.error(f":x: {message}")
            return False
        
        logger.info("=" * 60)
        logger.info("Migración de sistema de archivos completado con éxito!")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f":x: Error al migrar sistema de archivos: {str(e)}")
        return False
