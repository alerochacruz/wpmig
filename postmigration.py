"""
Módulo de tareas posteriores a la migración para migraciones de sitios WordPress.

Este módulo gestiona las actualizaciones finales de configuración una vez que
la migración de la base de datos y del sistema de archivos se ha completado.
Actualiza wp-config.php con las nuevas credenciales de la base de datos,
regenera las claves de seguridad y salts, configura el modo de depuración y
verifica el archivo de configuración.

Funciones:
    generate_salt: Genera un salt aleatorio para las claves de seguridad de WordPress.
    update_database_credentials: Actualiza la configuración de la base de datos en wp-config.php.
    update_security_keys: Regenera todas las claves de seguridad y salts de WordPress.
    set_debug_mode: Activa o desactiva el modo de depuración de WordPress.
    verify_wp_config: Verifica que wp-config.php sea válido y legible.
    run_post_migration_tasks: Ejecuta todas las tareas de configuración posteriores a la migración.

Ejemplo:
    from postmigration import run_post_migration_tasks
    
    success = run_post_migration_tasks(
        dest_ssh=dest_ssh,
        wp_path=source_wp_path,
        db_creds=dest_creds,
        enable_debug=False
    )
"""

import paramiko
import logging
import sys
import secrets
import string

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
        command: Comanado a ejecutar.
    
    Returns:
        Tupla con (exit_code, stdout, stderr).
    """
    stdin, stdout, stderr = ssh_client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, stdout.read().decode().strip(), stderr.read().decode().strip()


def generate_salt() -> str:
    """
    Genera una salt aleatoria para las claves de seguridad de WordPress.
    
    Returns:
        Cadena aleatoria de 64 caracteres.
    """
    characters = string.ascii_letters + string.digits + '!@#$%^&*()-_=+[]{}|;:,.<>?'
    return ''.join(secrets.choice(characters) for _ in range(64))


def update_database_credentials(dest_ssh: paramiko.SSHClient,
                                wp_path: str,
                                db_creds: dict) -> tuple:
    """
    Actualiza credenciales de base de datos en wp-config.php.
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        wp_path: Ruta de instalación de WordPress.
        db_creds: Diccionario con db_name, db_user, db_pass, db_host.
    
    Returns:
        Tupla con (success, message).
    """
    logger.info("=" * 60)
    logger.info("Actualizando las credenciales de la base de datos en wp-config.php")
    logger.info("=" * 60)
    
    wp_config_path = f"{wp_path}/wp-config.php"
    
    logger.info(f"Archivo de configuración: {wp_config_path}")
    logger.info(f"Nueva base de datos: {db_creds['db_name']}")
    logger.info(f"Nuevo host de base de datos: {db_creds['db_host']}")
    
    # Actualizar DB_NAME
    logger.info("\nActualizando DB_NAME...")
    sed_cmd = f"sed -i \"s/define( *'DB_NAME'.*/define( 'DB_NAME', '{db_creds['db_name']}' );/\" {wp_config_path}"
    exit_code, _, stderr = execute_remote_command(dest_ssh, sed_cmd)
    if exit_code != 0:
        return False, f"Error al actualizar DB_NAME: {stderr}"
    logger.info(":✓: DB_NAME actualizado")
    
    # Actualizar DB_USER
    logger.info("Actualizando DB_USER...")
    sed_cmd = f"sed -i \"s/define( *'DB_USER'.*/define( 'DB_USER', '{db_creds['db_user']}' );/\" {wp_config_path}"
    exit_code, _, stderr = execute_remote_command(dest_ssh, sed_cmd)
    if exit_code != 0:
        return False, f"Error al actualizar DB_USER: {stderr}"
    logger.info(":✓: DB_USER actualizado")
    
    # Actualizar DB_PASSWORD
    logger.info("Actualizando DB_PASSWORD...")
    # Escape special characters in password
    escaped_pass = db_creds['db_pass'].replace("'", "'\\''")
    sed_cmd = f"sed -i \"s/define( *'DB_PASSWORD'.*/define( 'DB_PASSWORD', '{escaped_pass}' );/\" {wp_config_path}"
    exit_code, _, stderr = execute_remote_command(dest_ssh, sed_cmd)
    if exit_code != 0:
        return False, f"Error al actualizar DB_PASSWORD: {stderr}"
    logger.info(":✓: DB_PASSWORD actualizado")
    
    # Actualizar DB_HOST
    logger.info("Actualizando DB_HOST...")
    sed_cmd = f"sed -i \"s/define( *'DB_HOST'.*/define( 'DB_HOST', '{db_creds['db_host']}' );/\" {wp_config_path}"
    exit_code, _, stderr = execute_remote_command(dest_ssh, sed_cmd)
    if exit_code != 0:
        return False, f"Error al actualizar DB_HOST: {stderr}"
    logger.info(":✓: DB_HOST actualizado")
    
    return True, "Credenciales de base de datos actualizadas con éxito"


def update_security_keys(dest_ssh: paramiko.SSHClient,
                        wp_path: str) -> tuple:
    """
    Actualiza las claves de seguridad y salts de WordPress en wp-config.php
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        wp_path: Ruta de instalación de WordPress.
    
    Returns:
        Tupla con (success, message).
    """
    logger.info("=" * 60)
    logger.info("Actualizando claves de seguridad y salts de WordPress")
    logger.info("=" * 60)
    
    wp_config_path = f"{wp_path}/wp-config.php"
    
    # Generar nuevas salts
    salts = {
        'AUTH_KEY': generate_salt(),
        'SECURE_AUTH_KEY': generate_salt(),
        'LOGGED_IN_KEY': generate_salt(),
        'NONCE_KEY': generate_salt(),
        'AUTH_SALT': generate_salt(),
        'SECURE_AUTH_SALT': generate_salt(),
        'LOGGED_IN_SALT': generate_salt(),
        'NONCE_SALT': generate_salt()
    }
    
    logger.info("Generando nuevas claves de seguridad y salts...")
    
    # Actualizar cada salt utilizando sed
    for key_name, key_value in salts.items():
        logger.info(f"  - Actualizando {key_name}...")
        
        # Primero, escapar cualquier caracter especial que pueda estar en la salt
        escaped_value = key_value.replace("'", "'\\''").replace("/", "\\/").replace("&", "\\&")
        
        # Utilizar un comando de sed que coincida con la línea completa y la reemplace
        sed_cmd = f"sed -i \"/define([[:space:]]*'{key_name}'/c\\define( '{key_name}', '{escaped_value}' );\" {wp_config_path}"
        exit_code, _, stderr = execute_remote_command(dest_ssh, sed_cmd)
        
        if exit_code != 0:
            logger.warning(f":!: No se pudo actualizar {key_name}: {stderr}")
    
    logger.info(":✓: Claves de seguridad y salts regeneradas")
    
    return True, "Claves de seguridad actualizadas con éxito"


def set_debug_mode(dest_ssh: paramiko.SSHClient,
                  wp_path: str,
                  enable_debug: bool = False) -> tuple:
    """
    Habilita o deshabilita WordPress debug mode.
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        wp_path: Ruta de instalación de WordPress.
        enable_debug: Si habilitar o no debug mode.
    
    Returns:
        Tupla con (success, message)
    """
    logger.info("=" * 60)
    logger.info("Configurando WordPress Debug Mode")
    logger.info("=" * 60)
    
    wp_config_path = f"{wp_path}/wp-config.php"
    
    debug_value = "true" if enable_debug else "false"
    logger.info(f"Estableciendo WP_DEBUG a: {debug_value}")
    
    # Verificar si WP_DEBUG ya existe
    exit_code, output, _ = execute_remote_command(
        dest_ssh,
        f"grep -c 'WP_DEBUG' {wp_config_path} || true"
    )
    
    if output and int(output) > 0:
        # Actualizar WP_DEBUG existente
        sed_cmd = f"sed -i \"s/define( *'WP_DEBUG'.*/define( 'WP_DEBUG', {debug_value} );/\" {wp_config_path}"
        exit_code, _, stderr = execute_remote_command(dest_ssh, sed_cmd)
        
        if exit_code != 0:
            return False, f"Error al actualizar WP_DEBUG: {stderr}"
        
        logger.info(":✓: WP_DEBUG actualizado")
    else:
        # Agregar WP_DEBUG antes de la línea "That's all, stop editing!"
        logger.info("Agregando configuración de WP_DEBUG...")
        insert_cmd = f"sed -i \"/That's all, stop editing/i define( 'WP_DEBUG', {debug_value} );\" {wp_config_path}"
        exit_code, _, stderr = execute_remote_command(dest_ssh, insert_cmd)
        
        if exit_code != 0:
            return False, f"Error al agregar WP_DEBUG: {stderr}"
        
        logger.info(":✓: WP_DEBUG agregado")
    
    # Agregar WP_DEBUG_LOG y WP_DEBUG_DISPLAY si el debug está habilitado
    if enable_debug:
        logger.info("Configurando debug logging...")
        
        # Verificar y agregar WP_DEBUG_LOG
        exit_code, output, _ = execute_remote_command(
            dest_ssh,
            f"grep -c 'WP_DEBUG_LOG' {wp_config_path} || true"
        )
        
        if not output or int(output) == 0:
            insert_cmd = f"sed -i \"/WP_DEBUG/a define( 'WP_DEBUG_LOG', true );\" {wp_config_path}"
            execute_remote_command(dest_ssh, insert_cmd)
            logger.info(":✓: WP_DEBUG_LOG activado")
        
        # Verificar y agregar WP_DEBUG_DISPLAY
        exit_code, output, _ = execute_remote_command(
            dest_ssh,
            f"grep -c 'WP_DEBUG_DISPLAY' {wp_config_path} || true"
        )
        
        if not output or int(output) == 0:
            insert_cmd = f"sed -i \"/WP_DEBUG_LOG/a define( 'WP_DEBUG_DISPLAY', false );\" {wp_config_path}"
            execute_remote_command(dest_ssh, insert_cmd)
            logger.info(":✓: WP_DEBUG_DISPLAY configurado")
    
    return True, f"Debug mode {'enabled' if enable_debug else 'disabled'}"


def verify_wp_config(dest_ssh: paramiko.SSHClient,
                    wp_path: str) -> tuple:
    """
    Verifica si wp-config.php es válido y legible.
    
    Args:
        dest_ssh: Cliente SSH conectado a destino.
        wp_path: Ruta de instalación de WordPress.
    
    Returns:
        Tuple con (success, message).
    """
    logger.info("=" * 60)
    logger.info("Validando wp-config.php")
    logger.info("=" * 60)
    
    wp_config_path = f"{wp_path}/wp-config.php"
    
    # Verificar si existe archivo
    logger.info("Validando si wp-config.php existe...")
    exit_code, _, _ = execute_remote_command(
        dest_ssh,
        f"test -f {wp_config_path} && echo 'exists'"
    )
    
    if exit_code != 0:
        return False, "wp-config.php no encontrado"
    
    logger.info(":✓: wp-config.php existe")
    
    # Verificar permisos de archivo
    logger.info("Validando permisos de archivo...")
    exit_code, perms, _ = execute_remote_command(
        dest_ssh,
        f"stat -c '%a' {wp_config_path}"
    )
    
    if exit_code == 0:
        logger.info(f":✓: Permisos de archivo: {perms}")
    
    # Verificar sintaxis de PHP
    logger.info("Validando sintaxis de PHP...")
    exit_code, output, stderr = execute_remote_command(
        dest_ssh,
        f"php -l {wp_config_path}"
    )
    
    if exit_code != 0:
        return False, f"Error de sintaxis PHP en wp-config.php: {stderr}"
    
    logger.info(":✓: La sintaxis de PHP es válida")
    
    return True, "wp-config.php verificado con éxito"


def run_post_migration_tasks(dest_ssh: paramiko.SSHClient,
                             wp_path: str,
                             db_creds: dict,
                             enable_debug: bool = False) -> bool:
    """
    Flujo de trabajo post-migración completo.
    
    Args:
        dest_ssh: Cliente SSH conectado a servidor destino.
        wp_path: Ruta de instalación de WordPRess en destino.
        db_creds: Diccionario con credenciales de base datos.
        enable_debug: Si habilitar o no debug mode.
    
    Returns:
        Booleano. True si todas las tareas se completan con
        éxito, False en caso contrario.
    """
    logger.info("=" * 60)
    logger.info("Comenzando tareas post-migración")
    logger.info("=" * 60)
    
    try:
        # Paso 1: Actualizar credenciales de base de datos
        success, message = update_database_credentials(dest_ssh, wp_path, db_creds)
        if not success:
            logger.error(f":x: {message}")
            return False
        logger.info(f":✓: {message}")
        
        # Paso 2: Actualizar claves de seguridad y salts
        success, message = update_security_keys(dest_ssh, wp_path)
        if not success:
            logger.error(f":x: {message}")
            return False
        logger.info(f":✓: {message}")
        
        # Paso 3: Establecer debug mode
        success, message = set_debug_mode(dest_ssh, wp_path, enable_debug)
        if not success:
            logger.error(f":x: {message}")
            return False
        logger.info(f":✓: {message}")
        
        # Paso 4: Verificar wp-config.php
        success, message = verify_wp_config(dest_ssh, wp_path)
        if not success:
            logger.error(f":x: {message}")
            return False
        logger.info(f":✓: {message}")
        
        logger.info("=" * 60)
        logger.info("Tareas post-migración completadas con éxito!")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f":x: Error en las tareas post-migración: {str(e)}")
        return False
