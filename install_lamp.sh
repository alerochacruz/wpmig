#!/bin/bash

set -e
export DEBIAN_FRONTEND=noninteractive

# =============================================================================
# CONSTANTES
# =============================================================================
WEBSERVER_IP="192.168.0.251"
WP_DOCROOT="/var/www/html/"
# =============================================================================

# 1. Actualizar el índice local de paquetes
sudo apt update

# 2. Instalar servidor web Apache
sudo apt --yes install apache2

# 3. Instalar servidor de bases de datos MariaDB
sudo apt --yes install mariadb-server

# 4. Mejorar seguridad de MariaDB
# https://mariadb.com/docs/server/clients-and-utilities/legacy-clients-and-utilities/mysql_secure_installation
sudo mariadb << EOF
-- Eliminar cuentas sin nombre de usuario, ya que representan un riesgo de acceso no autorizado
DELETE FROM mysql.user WHERE User='';
-- Restringir el acceso del usuario root únicamente a direcciones locales
-- (evita intentos de conexión remota con credenciales privilegiadas)
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
-- Eliminar la base de datos de pruebas 'test', que suele venir por defecto
-- y podría ser utilizada para ataques o abusos
DROP DATABASE IF EXISTS test;
-- Eliminar todos los permisos asociados a la base 'test' y sus variantes
DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
-- Forzar recarga de privilegios para aplicar cambios
FLUSH PRIVILEGES;
EOF

# 5. Instalar el intérprete de PHP
sudo apt --yes install php

# 6. Instalar extensiones de PHP necesarias para WordPress
# https://make.wordpress.org/hosting/handbook/server-environment/
sudo apt --yes install libapache2-mod-php php-mysql php-cli php-zip php-curl php-xml
sudo apt --yes install php-gd php-imagick
sudo systemctl restart apache2

# 7. Configurar el usuario del proceso de Apache (www-data) como propietario del directorio
sudo chown -R www-data:www-data $WP_DOCROOT

# Asignar permisos de directorio
# rwx r-x r-x
sudo find $WP_DOCROOT -type d -exec chmod 755 {} \;

# Asignar permisos de archivo
# rwx r-- r--
sudo find $WP_DOCROOT -type f -exec chmod 644 {} \;
 
# 8. Instalar otros paquetes de uso común
sudo apt --yes install curl wget

# 9. Mensaje de instalación exitosa
echo -e "\n======================================================================"
echo "¡El stack LAMP se ha instalado con éxito!"
echo -e "======================================================================\n"
