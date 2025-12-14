"""
Herramienta de Migración de WordPress - Punto de entrada principal.

Este es el script principal que orquesta el flujo completo de migración de un
sitio WordPress. Guía al usuario a través de una configuración interactiva,
realiza las validaciones necesarias y ejecuta la migración de la base de datos,
la migración del sistema de archivos y las tareas posteriores a la migración
de forma secuencial.

El flujo de migración consta de:
    1. Recolección interactiva de la configuración de los servidores.
    2. Validación previa a la migración de ambos servidores.
    3. Exportación, transferencia e importación de la base de datos.
    4. Transferencia de archivos de WordPress con copia de seguridad.
    5. Actualizaciones de configuración posteriores a la migración.

Uso:
    python main.py

El script solicitará de forma interactiva toda la información necesaria,
incluyendo credenciales del servidor, detalles de la base de datos y parámetros
de migración. Todas las operaciones se registran en wp_migration.log para facilitar
la resolución de problemas.

Requisitos:
    - paramiko: conectividad SSH
    - Python 3.6+: f-strings y anotaciones de tipo
    - Acceso a los servidores de origen y destino vía SSH
"""

import sys
from config import collect_server_configurations
from validation import run_pre_migration_validation, create_ssh_connection
from database import run_database_migration
from filesystem import run_filesystem_migration
from postmigration import run_post_migration_tasks
from dotenv import load_dotenv
load_dotenv()
import os

def main():
    """Flujo de trabajo de migración principal"""
    source_ssh = None
    dest_ssh = None
    
    try:
        # Paso 1: Recolectar configuraciones del servidor interactivamente
        source_config, dest_config = collect_server_configurations()
        
        # Paso 2: Ejecutar validación pre-migración
        print("\n" + "=" * 60)
        print("Ejecutando validación pre-migración...")
        print("=" * 60)
        
        if not run_pre_migration_validation(source_config, dest_config):
            print("\n:x: Validación fallida. No se puede proseguir con la migración.")
            sys.exit(1)
        
        print("\n:✓: Todas las validaciones se pasaron con éxito!")
        
        # Paso 3: Crear conexiones SSH para migración
        print("\nEstableciendo conexión SSH para la migración...")
        source_ssh = create_ssh_connection(source_config)
        dest_ssh = create_ssh_connection(dest_config)
        print(":✓: Conexión SSH establecida")
        
        # Paso 4: Obtener parámetros de migración
        print("\n" + "=" * 60)
        print("Configuración de la migración")
        print("=" * 60)

        # Cargar valores predeterminados de .env (si está presente)
        env_old_url = os.getenv("OLD_URL", "")
        env_new_url = os.getenv("NEW_URL", "")
        env_source_wp_path = os.getenv("SOURCE_WP_PATH", "/var/www/html")

        # Preguntar al usuario usando los valores de .env como predeterminados
        old_url = input(
            f"\nIngrese URL anterior (ej. https://misitio.com) [{env_old_url}]: "
        ).strip() or env_old_url

        new_url = input(
            f"Ingrese URL nueva (ej. https://misitio.com) [{env_new_url}]: "
        ).strip() or env_new_url

        source_wp_path = input(
            f"Ruta de origen de WordPress [{env_source_wp_path}]: "
        ).strip() or env_source_wp_path
       
        # Paso 5: Ejecutar migración de base de datos
        print("\n" + "=" * 60)
        print("Comenzando migración de base de datos...")
        print("=" * 60)
        
        db_success, dest_creds = run_database_migration(
            source_ssh=source_ssh,
            dest_ssh=dest_ssh,
            source_wp_path=source_wp_path,
            old_url=old_url,
            new_url=new_url
        )
        
        if not db_success:
            print("\n:x: Error en la migración de base de datos. Abortando.")
            sys.exit(1)
        
        print("\n:✓: Migración de base de datos completada!")
        
        # Paso 6: Ejecutar migración de sistema de archivos
        print("\n" + "=" * 60)
        print("Comenzando migración de sistema de archivos...")
        print("=" * 60)
        
        fs_success = run_filesystem_migration(
            source_ssh=source_ssh,
            dest_ssh=dest_ssh,
            source_config=source_config,
            dest_config=dest_config,
            create_backup=True
        )
        
        if not fs_success:
            print("\n:x: Error en la migración de sistema de archivos")
            sys.exit(1)
        
        print("\n:✓: Migración de sistema de archivos completada!")
        
        # Paso 7: Ejectuar tareas post-migración
        print("\n" + "=" * 60)
        print("Comenzando tareas post-migración...")
        print("=" * 60)
        
        post_success = run_post_migration_tasks(
            dest_ssh=dest_ssh,
            wp_path=source_wp_path,
            db_creds=dest_creds,
            enable_debug=False
        )
        
        if not post_success:
            print("\n:x: Error en las tareas post-migración.")
            print("   Bases de datos y archivos migrados, pero wp-config.php puede requerir actualización manual.")
            sys.exit(1)
        
        print("\n:✓: Tareas post-migración completadas!")
        
        # ¡Éxito!
        print("\n" + "=" * 60)
        print(":✓: Migración de WordPress completada con éxito!")
        print("=" * 60)
        print(f"\nSu sitio WordPress debería ser accesible en: {new_url}")
        print("Por favor verifique que el sitio está funcionando correctamente.")
        print(f"\nLog de migración guardado en: wp_migration.log")
        
        sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n:x: Operación cancelada por el usuario (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print(f"\n:x: Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Siempre cerrar conexiones SSH
        if source_ssh:
            source_ssh.close()
        if dest_ssh:
            dest_ssh.close()


if __name__ == "__main__":
    main()
