"""
Módulo de migración de bases de datos para migraciones de sitios WordPress.

Este módulo gestiona el flujo completo de migración de la base de datos,
incluyendo la exportación, transferencia, importación y actualización de URLs.
Utiliza mysqldump para la exportación, SFTP para la transferencia y el cliente
mysql para la importación.

Funciones:
    get_database_credentials: Extrae las credenciales de la base de datos desde wp-config.php
    export_database: Crea un volcado MySQL comprimido de la base de datos de WordPress
    transfer_database_dump: Transfiere el archivo de volcado del origen al destino
    import_database: Importa el volcado de la base de datos en el MySQL de destino
    update_site_urls: Actualiza las URLs de WordPress en la base de datos (buscar y reemplazar)
    get_destination_db_credentials: Solicita al usuario las credenciales de la BD de destino
    run_database_migration: Ejecuta el flujo completo de migración de la base de datos

Ejemplo:
    from database import run_database_migration
    
    success, dest_creds = run_database_migration(
        source_ssh=source_ssh,
        dest_ssh=dest_ssh,
        source_wp_path="/var/www/html",
        old_url="http://url-anterior.com",
        new_url="http://url-nueva.com"
    )
"""

import paramiko
import logging
import sys
import re
from datetime import datetime
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
    Ejecuta comando en un servidor remoto vía SSH.
    
    Args:
        ssh_client: Cliente SSH conectado.
        command: Comando a ejecutar.
    
    Returns:
        Tupla con (exit_code, stdout, stderr).
    """
    stdin, stdout, stderr = ssh_client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, stdout.read().decode().strip(), stderr.read().decode().strip()


def get_database_credentials(ssh_client: paramiko.SSHClient, 
                             wp_path: str) -> dict:
    """
    Extrae credenciales de base de datos de wp-config.php.
    
    Args:
        ssh_client: Cliente SSH conectado.
        wp_path: Ruta a la instalación de WordPress.
    
    Returns:
        Dictionary with database credentials
        Diccionario con credenciales de la base de datos.
    
    Raises:
        Exception: If credentials cannot be extracted
    """
    logger.info("Extrayendo credenciales de base de datos de wp-config.php...")
    
    commands = {
        'db_name': f"grep \"DB_NAME\" {wp_path}/wp-config.php | cut -d\\' -f4",
        'db_user': f"grep \"DB_USER\" {wp_path}/wp-config.php | cut -d\\' -f4",
        'db_pass': f"grep \"DB_PASSWORD\" {wp_path}/wp-config.php | cut -d\\' -f4",
        'db_host': f"grep \"DB_HOST\" {wp_path}/wp-config.php | cut -d\\' -f4",
    }
    
    creds = {}
    for key, cmd in commands.items():
        exit_code, value, _ = execute_remote_command(ssh_client, cmd)
        if exit_code == 0 and value:
            creds[key] = value
        else:
            raise Exception(f"No se pudo extraer {key} de wp-config.php")
    
    logger.info(f":✓: Credenciales de base datos extraída: {creds['db_name']} @ {creds['db_host']}")
    return creds


def export_database(ssh_client: paramiko.SSHClient, 
                   db_creds: dict,
                   backup_path: str) -> tuple:
    """
    Exporta base de datos MySQL/MariaDB utilizando mysqldump.
    
    Args:
        ssh_client: Cliente SSH conectado.
        db_creds: Credenciales de base de datos.
        backup_path: Ruta donde guardar el archivo de volcado.
    
    Returns:
        Tupla con (success, message, dump_file_path)
    """
    logger.info("=" * 60)
    logger.info("Comenzando exportación de base de datos")
    logger.info("=" * 60)
    
    # Generar nombre the archivo con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_filename = f"wordpress_db_{timestamp}.sql"
    dump_file = f"{backup_path}/{dump_filename}"
    compressed_file = f"{dump_file}.gz"
    
    logger.info(f"Base de datos: {db_creds['db_name']}")
    logger.info(f"Archivo de volcado: {compressed_file}")
    
    # Crear directorio de backup si no existe
    logger.info("\nCreando directorio de backup...")
    exit_code, _, stderr = execute_remote_command(
        ssh_client,
        f"mkdir -p {backup_path}"
    )
    if exit_code != 0:
        return False, f"Error al crear el directorio de backup: {stderr}", ""
    
    logger.info(":✓: Directorio de backup listo")
    
    # Exportar base de datos con mysqldump
    logger.info("\nExportando base de datos (esto puede tomar un tiempo)...")
    mysqldump_cmd = (
        f"mysqldump "
        f"-h {db_creds['db_host']} "
        f"-u {db_creds['db_user']} "
        f"-p'{db_creds['db_pass']}' "
        f"{db_creds['db_name']} "
        f"> {dump_file} 2>&1"
    )
    
    exit_code, output, stderr = execute_remote_command(ssh_client, mysqldump_cmd)
    
    if exit_code != 0:
        return False, f"Error al exportar la base de datos: {output} {stderr}", ""
    
    logger.info(":✓: Base de datos exportada con éxito")
    
    # Comprimir el archivo de volcado
    logger.info("\nComprimiendo volcado de base de datos...")
    exit_code, _, stderr = execute_remote_command(
        ssh_client,
        f"gzip {dump_file}"
    )
    
    if exit_code != 0:
        return False, f"Error al comprimir: {stderr}", ""
    
    # Obtener tamaño del archivo comprimido
    exit_code, file_size, _ = execute_remote_command(
        ssh_client,
        f"du -h {compressed_file} | cut -f1"
    )
    
    logger.info(f":✓: Base de datos comprimida con éxito ({file_size})")
    
    return True, f"Base de datos expoprtada y comprimida: {compressed_file}", compressed_file


def transfer_database_dump(source_ssh: paramiko.SSHClient,
                           dest_ssh: paramiko.SSHClient,
                           dump_file: str,
                           dest_path: str) -> tuple:
    """
    Transfiere el volcado de la base de datos de origen a destino utilizando
    un enfoque similar a SCP.
    
    Args:
        source_ssh: Cliente SSH conectado a origen.
        dest_ssh: Cliente SSH conectado a destino.
        dump_file: Ruta al archivo de volcado en el servidor origen.
        dest_path: Ruta de destino en el servidor destino.
    
    Returns:
        Tuple of (success, message, dest_file_path)
    """
    logger.info("=" * 60)
    logger.info("Transfiriendo volcado de base de datos")
    logger.info("=" * 60)
    
    # Extract filename from path
    filename = dump_file.split('/')[-1]
    dest_file = f"{dest_path}/{filename}"
    
    logger.info(f"Origen: {dump_file}")
    logger.info(f"Destino: {dest_file}")
    
    # Create destination directory
    logger.info("\nPreparando directorio de destino...")
    exit_code, _, stderr = execute_remote_command(
        dest_ssh,
        f"mkdir -p {dest_path}"
    )
    
    if exit_code != 0:
        return False, f"Error al crear directorio de destino: {stderr}", ""
    
    logger.info(":✓: Directorio de destino listo")
    
    # Transferir archivo utilizando SFTP
    logger.info("\nTransfiriendo archivo (esto puede tomar un tiempo)...")
    try:
        # Abrir sesiones SFTP
        source_sftp = source_ssh.open_sftp()
        dest_sftp = dest_ssh.open_sftp()
        
        # Descargar de origen al buffer de memoria y subir a destino
        # Para archivos grandes, se utilizar un archivo local temporal
        local_temp = f"/tmp/{filename}"
        
        # Descargar de origen
        logger.info("  - Descargando del servidor origen...")
        source_sftp.get(dump_file, local_temp)
        
        # Subir a destino
        logger.info("  - Subiendo al servidor destino...")
        dest_sftp.put(local_temp, dest_file)
        
        # Eliminar archivo temporal
        os.remove(local_temp)
        
        # Cerrar conexiones SFPT
        source_sftp.close()
        dest_sftp.close()
        
        # Verificar archivo en destino
        exit_code, file_size, _ = execute_remote_command(
            dest_ssh,
            f"du -h {dest_file} | cut -f1"
        )
        
        logger.info(f":✓: Transferencia completada con éxito ({file_size})")
        
        return True, f"Volcado de base de datos transferida: {dest_file}", dest_file
        
    except Exception as e:
        return False, f"Error en la transferencia: {str(e)}", ""


def get_destination_db_credentials(dest_ssh: paramiko.SSHClient) -> dict:
    """
    Obtiene las credenciales de la base de datos para el servidor de destino.
    Las variables de entorno (por ejemplo, DESTINATION_DB_NAME, DESTINATION_DB_USER, etc.)
    se utilizan como valores predeterminados cuando están disponibles. Cuando no lo están,
    la función solicita los datos al usuario de forma interactiva.

    Args:
        dest_ssh: Cliente SSH conectado al servidor de destino.

    Returns:
        Diccionario con las credenciales de la base de datos del servidor destino.
    """
    logger.info("=" * 60)
    logger.info("Configuración de la base de datos de destino")
    logger.info("=" * 60)

    print("\nIngrese las credenciales de la base de datos de destino:")

    # Cargar valores predeterminados desde las variables de entorno (si están presentes)
    default_name = os.getenv("DESTINATION_DB_NAME", "wordpress_db")
    default_user = os.getenv("DESTINATION_DB_USER", "wordpress_user")
    default_pass = os.getenv("DESTINATION_DB_PASS")  # sin default fallback por seguridad
    default_host = os.getenv("DESTINATION_DB_HOST", "localhost")

    dest_creds = {}

    # Nombre de la base datos
    dest_creds['db_name'] = (
        input(f"Nombre de la base de datos [{default_name}]: ").strip() or default_name
    )

    # Usuario de la base datos
    dest_creds['db_user'] = (
        input(f"Usuario de la base de datos [{default_user}]: ").strip() or default_user
    )

    # Contraseña de la base de datos
    import getpass
    if default_pass:
        # Si la contraseña es proviste en .env, no preguntar al usuario
        dest_creds['db_pass'] = default_pass
    else:
        dest_creds['db_pass'] = getpass.getpass("Contraseña de la base de datos: ")

    # Host de la base de datos
    dest_creds['db_host'] = (
        input(f"Host de la base de datos [{default_host}]: ").strip() or default_host
    )

    return dest_creds


def create_destination_database(dest_ssh: paramiko.SSHClient,
                               dest_creds: dict,
                               mysql_root_pass: str = None) -> tuple:
    """
    Crea base de datos y usuario en servidor destino.
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        dest_creds: Credenciales de base de datos de destino.
        mysql_root_pass: Contraseña root de MySQL/MariaDB (si está disponible).
    
    Returns:
        Tupla con (success, message)
    """
    logger.info("=" * 60)
    logger.info("Creando base de datos de destino")
    logger.info("=" * 60)
    
    # Verificar si la base de datos ya existe
    logger.info(f"Validando si la base de datos '{dest_creds['db_name']}' existe...")
    
    if mysql_root_pass:
        root_auth = f"-p'{mysql_root_pass}'"
    else:
        # Intentar sin contraseña (algunos sistemas tienen auth_socket)
        root_auth = ""
    
    check_db_cmd = (
        f"mysql -u root {root_auth} "
        f"-e \"SHOW DATABASES LIKE '{dest_creds['db_name']}';\" 2>&1"
    )
    
    exit_code, output, _ = execute_remote_command(dest_ssh, check_db_cmd)
    
    if dest_creds['db_name'] in output:
        logger.info(f":!: La base de datos '{dest_creds['db_name']}' ya existe")
        return True, "La base de datos ya existe"
    
    # Crear usuario de base de datos
    logger.info(f"Creando base de datos y usuario...")
    
    create_db_cmd = f"""
mysql -u root {root_auth} <<EOF
CREATE DATABASE IF NOT EXISTS {dest_creds['db_name']};
CREATE USER IF NOT EXISTS '{dest_creds['db_user']}'@'localhost' IDENTIFIED BY '{dest_creds['db_pass']}';
GRANT ALL PRIVILEGES ON {dest_creds['db_name']}.* TO '{dest_creds['db_user']}'@'localhost';
FLUSH PRIVILEGES;
EOF
"""
    
    exit_code, output, stderr = execute_remote_command(dest_ssh, create_db_cmd)
    
    if exit_code != 0:
        return False, f"Error al crear la base de datos: {output} {stderr}"
    
    logger.info(f":✓: La base de datos '{dest_creds['db_name']}' se creó con éxito")
    return True, "Base de datos creada con éxito"


def import_database(dest_ssh: paramiko.SSHClient,
                   dest_creds: dict,
                   dump_file: str) -> tuple:
    """
    Importa archivo de volcado en base de datos MySQL/MariaDB destino.
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        dest_creds: Credenciales de base de datos de destino.
        dump_file: Ruta al archivo de volcado comprimido en destino.
    
    Returns:
        Tupla con (success, message).
    """
    logger.info("=" * 60)
    logger.info("Importando base de datos")
    logger.info("=" * 60)
    
    logger.info(f"Base de datos: {dest_creds['db_name']}")
    logger.info(f"Archivo de volcado: {dump_file}")
    
    # Descomprimir archivo de volcado
    logger.info("\nDescomprimiendo volcado de base de datos...")
    uncompressed_file = dump_file.replace('.gz', '')
    
    exit_code, _, stderr = execute_remote_command(
        dest_ssh,
        f"gunzip -c {dump_file} > {uncompressed_file}"
    )
    
    if exit_code != 0:
        return False, f"Error al descomprimir: {stderr}"
    
    logger.info(":✓: Volcado de base de datos descomprimida")
    
    # Importar base de datos
    logger.info("\nImporting database (this may take a while)...")
    logger.info("\nImportando base de datos (esto puede tomar un tiempo)...")
    
    import_cmd = (
        f"mysql "
        f"-h {dest_creds['db_host']} "
        f"-u {dest_creds['db_user']} "
        f"-p'{dest_creds['db_pass']}' "
        f"{dest_creds['db_name']} "
        f"< {uncompressed_file} 2>&1"
    )
    
    exit_code, output, stderr = execute_remote_command(dest_ssh, import_cmd)
    
    if exit_code != 0:
        return False, f"Error al importar base de datos: {output} {stderr}"
    
    logger.info(":✓: Base de datos importada con éxito")
    
    # Limpiar archivo descomprimido
    logger.info("\nLimpiando archivos temporales...")
    execute_remote_command(dest_ssh, f"rm -f {uncompressed_file}")
    
    return True, "Base de datos importada con éxito"


def update_site_urls(dest_ssh: paramiko.SSHClient,
                    dest_creds: dict,
                    old_url: str,
                    new_url: str) -> tuple:
    """
    Actualiza la URL del sitio de WordPress en la base
    de datos (buscar-reemplazar).
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        dest_creds: Credenciales de base de datos de destino.
        old_url: URL de sitio anterior (ej. https://misitio.com)
        new_url: URL de sitio actual (ej. https://misitio.com)
    
    Returns:
        Tupla con (success, message).
    """
    logger.info("=" * 60)
    logger.info("Actualizando URLs del sitio")
    logger.info("=" * 60)
    
    logger.info(f"URL anterior: {old_url}")
    logger.info(f"URL nueva: {new_url}")
    
    # Actualizar tabla wp_options (siteurl y home)
    logger.info("\nActualizando la tabla wp_options...")
    
    update_cmd = f"""
mysql -h {dest_creds['db_host']} -u {dest_creds['db_user']} -p'{dest_creds['db_pass']}' {dest_creds['db_name']} <<EOF
UPDATE wp_options SET option_value = '{new_url}' WHERE option_name = 'siteurl';
UPDATE wp_options SET option_value = '{new_url}' WHERE option_name = 'home';
EOF
"""
    
    exit_code, output, stderr = execute_remote_command(dest_ssh, update_cmd)
    
    if exit_code != 0:
        return False, f"Error al actualizar URLs: {output} {stderr}"
    
    logger.info(":✓: URLs del sitio actualizadas con éxito")
    
    return True, "URLs actualizadas con éxito"


def run_database_migration(source_ssh: paramiko.SSHClient,
                          dest_ssh: paramiko.SSHClient,
                          source_wp_path: str,
                          old_url: str,
                          new_url: str) -> tuple:
    """
    Completa flujo de trabajo de migración de la base de datos.
    
    Args:
        source_ssh: Cliente SSH conectado a servidor origen.
        dest_ssh: Cliente SSH conectado a servidor destino.
        source_wp_path: Ruta con la instalación de WordPress en origen.
        old_url: URL de sitio anterior.
        new_url: URL de sitio actual.
    
    Returns:
        Tupla con (success: bool, dest_creds: dict).
    """
    backup_path = "/tmp/wp_migration_backup"
    
    try:
        # Paso 1: Obtener las credenciales de la base de datos de origen
        source_creds = get_database_credentials(source_ssh, source_wp_path)
        
        # Paso 2: Exportar la base de datos de origen
        success, message, dump_file = export_database(source_ssh, source_creds, backup_path)
        if not success:
            logger.error(f":x: {message}")
            return False, {}
        
        # Paso 3: Transferir el volcado a destino
        success, message, dest_dump = transfer_database_dump(
            source_ssh, dest_ssh, dump_file, backup_path
        )
        if not success:
            logger.error(f":x: {message}")
            return False, {}
        
        # Paso 4: Obtener las credenciales de la base de datos de destino
        dest_creds = get_destination_db_credentials(dest_ssh)
        
        # Paso 5: Crear la base de datos de destino (opcional - puede requerir la contraseña root)
        success, message = create_destination_database(dest_ssh, dest_creds)
        if not success:
            logger.warning(f":!: {message}")
            logger.warning("Es posible que necesite crear la base de datos manualmente")
        
        # Paso 6: Importar la base de datos a destino
        success, message = import_database(dest_ssh, dest_creds, dest_dump)
        if not success:
            logger.error(f":x: {message}")
            return False, {}
        
        # Paso 7: Actualizar URLs del sitio
        success, message = update_site_urls(dest_ssh, dest_creds, old_url, new_url)
        if not success:
            logger.error(f":x: {message}")
            return False, {}
        
        logger.info("=" * 60)
        logger.info("La migración de la base de datos se completó con éxito!")
        logger.info("=" * 60)
        
        return True, dest_creds
        
    except Exception as e:
        logger.error(f":x: Error al migrar la base de datos: {str(e)}")
        return False, {}
