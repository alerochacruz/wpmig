"""
Módulo de validación previa a la migración para migraciones de sitios WordPress.

Este módulo realiza comprobaciones exhaustivas tanto en el servidor de origen
como en el de destino antes de que comience la migración. Valida la conectividad
SSH, la instalación de WordPress, los componentes del stack LAMP, las credenciales
de la base de datos y el espacio en disco disponible.

Funciones:
    check_ssh_connectivity: Valida la conexión SSH a un servidor.
    check_wordpress_installation: Verifica que WordPress esté instalado.
    check_lamp_stack: Verifica que los componentes del stack LAMP estén en ejecución.
    check_database_credentials: Extrae y valida las credenciales de la base de datos.
    check_disk_space: Garantiza que haya suficiente espacio en disco en el destino.
    run_pre_migration_validation: Ejecuta todas las validaciones previas a la migración.

Ejemplo:
    from validation import run_pre_migration_validation
    
    success = run_pre_migration_validation(source_config, dest_config)
    if not success:
        print("La validación falló")
"""

import paramiko
import logging
import sys

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


def create_ssh_connection(config: dict) -> paramiko.SSHClient:
    """
    Crea una conexión SSH a un servidor.

    Args:
        config: Diccionario con 'host', 'port', 'username', 'password' o 'key_path'.

    Returns:
        paramiko.SSHClient: Cliente SSH conectado.

    Raises:
        Exception: Si la conexión falla.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    connect_params = {
        'hostname': config['host'],
        'port': config.get('port', 22),
        'username': config['username'],
        'timeout': 10
    }
    
    # Si es provista, utilizar llave SSH, sino utilizar contraseña
    if 'key_path' in config:
        connect_params['key_filename'] = config['key_path']
    else:
        connect_params['password'] = config['password']
    
    client.connect(**connect_params)
    return client


def execute_remote_command(ssh_client: paramiko.SSHClient, 
                           command: str) -> tuple:
    """
    Ejecuta comando en un servidor remoto vía SSH.
    
    Args:
        ssh_client: Cliente SSH conectado.
        command: Comando a ejectuar.
    
    Returns:
        Tupla con (exit_code, stdout, stderr).
    """
    stdin, stdout, stderr = ssh_client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, stdout.read().decode().strip(), stderr.read().decode().strip()


def check_ssh_connectivity(config: dict, server_name: str) -> tuple:
    """
    Valida una conexión SSH a un servidor.

    Args:
        config: Diccionario con la configuración de conexión del servidor.
        server_name: Nombre para logging (por ejemplo, "Origen" o "Destino").

    Returns:
        Tupla con (success, message, ssh_client o None).
    """
    try:
        ssh_client = create_ssh_connection(config)
        exit_code, hostname, _ = execute_remote_command(ssh_client, "hostname")
        return True, f"Conectado a servidor {server_name}: {hostname}", ssh_client
    except paramiko.AuthenticationException:
        return False, f"{server_name}: Autenticación fallida - verifique credenciales", None
    except paramiko.SSHException as e:
        return False, f"{server_name}: Error SSH: {str(e)}", None
    except Exception as e:
        return False, f"{server_name}: Error de conexión: {str(e)}", None


def check_wordpress_installation(ssh_client: paramiko.SSHClient) -> tuple:
    """
    Verifica si WordPress está instalado en el servidor.

    Args:
        ssh_client: Cliente SSH conectado.

    Returns:
        Una tupla con (success, message, wordpress_path o cadena vacía).
    """
    # Rutas comunes de instalación de WordPress
    wp_paths = ['/var/www/html', '/var/www/wordpress', '/usr/share/nginx/html']
    
    for path in wp_paths:
        exit_code, _, _ = execute_remote_command(
            ssh_client, 
            f"test -f {path}/wp-config.php && echo 'found'"
        )
        if exit_code == 0:
            # Intentar obtener versión de WordPress
            exit_code, wp_version, _ = execute_remote_command(
                ssh_client,
                f"grep \"\\$wp_version =\" {path}/wp-includes/version.php | cut -d\\' -f2"
            )
            
            if exit_code == 0 and wp_version:
                return True, f"WordPress {wp_version} encontrado en {path}", path
            else:
                return True, f"WordPress encontrado en {path} (versión desconocida)", path
    
    return False, "Instalación de WordPress no encontrada (wp-config.php faltante)", ""


def check_lamp_stack(ssh_client: paramiko.SSHClient) -> tuple:
    """
    Verifica que los componentes del LAMP stack estén instalados y en ejecución.

    Args:
        ssh_client: Cliente SSH conectado.

    Returns:
        Tupla con (success, message).
    """
    components = []
    missing = []
    
    # Verificar Apache o Nginx
    exit_code, _, _ = execute_remote_command(
        ssh_client, 
        "systemctl is-active apache2 2>/dev/null || systemctl is-active httpd 2>/dev/null"
    )
    if exit_code == 0:
        components.append("Apache")
    else:
        # Verificar Nginx como alaternativa
        exit_code, _, _ = execute_remote_command(
            ssh_client,
            "systemctl is-active nginx 2>/dev/null"
        )
        if exit_code == 0:
            components.append("Nginx")
        else:
            missing.append("Web Server (Apache/Nginx)")
    
    # Verificar MySQL/MariaDB
    exit_code, _, _ = execute_remote_command(
        ssh_client,
        "systemctl is-active mysql 2>/dev/null || systemctl is-active mariadb 2>/dev/null"
    )
    if exit_code == 0:
        components.append("MySQL/MariaDB")
    else:
        missing.append("MySQL/MariaDB")
    
    # Verificar PHP
    exit_code, php_version, _ = execute_remote_command(
        ssh_client,
        "php -v | head -n1 | awk '{print $2}'"
    )
    if exit_code == 0 and php_version:
        components.append(f"PHP {php_version}")
    else:
        missing.append("PHP")
    
    if missing:
        return False, f"Componentes faltantes: {', '.join(missing)}"
    else:
        return True, f"LAMP stack listo: {', '.join(components)}"


def check_database_credentials(ssh_client: paramiko.SSHClient, 
                                wp_path: str) -> tuple:
    """
    Extrae y valida las credenciales de base de datos desde wp-config.php.

    Args:
        ssh_client: Cliente SSH conectado.
        wp_path: Ruta a la instalación de WordPress.

    Returns:
        Una tupla con (success, message, credentials_dict o diccionario vacío).
    """
    # Extraer credenciales de base datos de wp-config.php
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
            return False, f"No se pudo extraer {key} de wp-config.php", {}
    
    # Verificar conexión de base de datos
    test_cmd = (
        f"mysql -h {creds['db_host']} -u {creds['db_user']} "
        f"-p'{creds['db_pass']}' -e 'USE {creds['db_name']}; "
        f"SELECT COUNT(*) FROM wp_posts;' 2>&1"
    )
    
    exit_code, output, _ = execute_remote_command(ssh_client, test_cmd)
    
    if exit_code == 0:
        return True, f"Base de datos '{creds['db_name']}' accesible", creds
    else:
        return False, f"No se pudo conectar a la base de datos: {output}", {}


def check_disk_space(source_ssh: paramiko.SSHClient, 
                     dest_ssh: paramiko.SSHClient,
                     wp_path: str) -> tuple:
    """
    Validar espacio de disco suficiente en servidor destino.
    
    Args:
        source_ssh: Cliente SSH conectado a origen.
        dest_ssh: Cliente SSH conectado a destino.
        wp_path: Ruta a WordPress en origen.
    
    Returns:
        Tupla con (success, message).
    """
    # Obtener tamaño de directorio (en MB) de WordPress de origen
    exit_code, source_size, _ = execute_remote_command(
        source_ssh,
        f"du -sm {wp_path} | awk '{{print $1}}'"
    )
    
    if exit_code != 0:
        return False, "No se pudo determinar el tamaño del directorio de origen"
    
    source_size_mb = int(source_size)
    
    # Obtener espacio disponible en desitno (en MB)
    exit_code, dest_avail, _ = execute_remote_command(
        dest_ssh,
        "df -m /var/www | tail -1 | awk '{print $4}'"
    )
    
    if exit_code != 0:
        return False, "No se pudo determinar el espacio disponible"
    
    dest_avail_mb = int(dest_avail)
    
    # Requerir almenos el doble del espacio de origen como recaudo
    required_mb = source_size_mb * 2
    
    if dest_avail_mb >= required_mb:
        return True, (f"Espacio suficiente: {dest_avail_mb}MB disponibles, "
                     f"{source_size_mb}MB requeridos ({required_mb}MB recomendado)")
    else:
        return False, (f"Espacio insuficiente: {dest_avail_mb}MB disponibles, "
                      f"{required_mb}MB requridos (origen: {source_size_mb}MB)")


def run_pre_migration_validation(source_config: dict, dest_config: dict) -> bool:
    """
    Ejecutar todas las validaciones pre-migración.
    
    Args:
        source_config: Configuración de servidor origen.
        dest_config: Configuración de servidor destino.
    
    Returns:
        Booleano. True si se pasan todas las validaciones, de otra forma False.
    """
    logger.info("=" * 60)
    logger.info("Comenzando validación pre-migración")
    logger.info("=" * 60)
    
    source_ssh = None
    dest_ssh = None
    wp_path = ""
    all_passed = True
    
    try:
        # 1. Verificar conectividad SSH a origen
        logger.info("\n[VALIDAR] Conectividad SSH - Origen...")
        success, message, source_ssh = check_ssh_connectivity(source_config, "Origen")
        if success:
            logger.info(f":✓: ÉXITO: {message}")
        else:
            logger.error(f":x: FALLA: {message}")
            all_passed = False
            return False  # Cannot continue without source connection
        
        # 2. Verificar conectividad SSH a destino
        logger.info("\n[VALIDAR] Conectividad SSH - Destino...")
        success, message, dest_ssh = check_ssh_connectivity(dest_config, "Destino")
        if success:
            logger.info(f":✓: ÉXITO: {message}")
        else:
            logger.error(f":x: FALLA: {message}")
            all_passed = False
            return False  # No puede continuar sin una conexión a destino
        
        # 3. Verificar instalación de WordPress en origen
        logger.info("\n[VALIDAR] Instalación de WordPress - Origen...")
        success, message, wp_path = check_wordpress_installation(source_ssh)
        if success:
            logger.info(f":✓: ÉXITO: {message}")
        else:
            logger.error(f":x: FALLA: {message}")
            all_passed = False
        
        # 4. Verificar LAMP stack en destino
        logger.info("\n[VALIDAR] LAMP Stack - Destino...")
        success, message = check_lamp_stack(dest_ssh)
        if success:
            logger.info(f":✓: ÉXITO: {message}")
        else:
            logger.error(f":x: FALLA: {message}")
            all_passed = False
        
        # 5. Verificar credenciales de base de datos en origen
        logger.info("\n[VALIDAR] Credenciales de base de datos - Origen...")
        if wp_path:  # Solo verificar si se encontró WordPress
            success, message, db_creds = check_database_credentials(source_ssh, wp_path)
            if success:
                logger.info(f":✓: ÉXITO: {message}")
            else:
                logger.error(f":x: FALLA: {message}")
                all_passed = False
        else:
            logger.warning(":!: OMITIR: ruta de WordPress no encontrada")
            all_passed = False
        
        # 7. Verificar espacio en disco en destino
        logger.info("\n[VALIDAR] Espacio de disco - Destino...")
        if wp_path:  # Solo verificar si se encontró WordPress
            success, message = check_disk_space(source_ssh, dest_ssh, wp_path)
            if success:
                logger.info(f":✓: ÉXITO: {message}")
            else:
                logger.error(f":x: FALLA: {message}")
                all_passed = False
        else:
            logger.warning(":!: OMITIR: Ruta de WordPress no encontrada")
            all_passed = False
        
        # Resumen
        logger.info("=" * 60)
        if all_passed:
            logger.info("Resumen de la validación: PRUEBAS EXITOSAS :✓:")
        else:
            logger.error("Resumen de la validación: ALGUNAS PRUEBAS FALLARON :x:")
        logger.info("=" * 60)
        
        return all_passed
        
    except Exception as e:
        logger.error(f"Error inesperado durante la validación: {str(e)}")
        return False
    
    finally:
        # Siempre cerrar conexiones SSH
        if source_ssh:
            source_ssh.close()
        if dest_ssh:
            dest_ssh.close()
