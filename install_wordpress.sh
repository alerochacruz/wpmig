#!/bin/bash

set -e
export DEBIAN_FRONTEND=noninteractive

# =============================================================================
# CONSTANTES
# =============================================================================
WEBSERVER_IP="192.168.0.250"
WP_DOCROOT="/var/www/html/"
DB_NAME="genesis_wpdb"
DB_USER="genesis_wpdbuser"
DB_PASS="genesis_wpdbpass"
DB_HOST="localhost"
ADMIN_USER="genesis_wpuser"
ADMIN_PASS="genesis_wppass"
ADMIN_EMAIL="momavac620@ergowiki.com"
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

# 9. Crear la base de datos para WordPress
sudo mariadb <<EOF
CREATE DATABASE $DB_NAME;
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
FLUSH PRIVILEGES;
EOF

# 10. Descargar e instalar la herrmaienta WPI-CLI
# https://github.com/wp-cli/wp-cli
curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
chmod +x wp-cli.phar
sudo mv wp-cli.phar /usr/local/bin/wp

# 11. WP-CLI: Descargar WordPress
# 2>/dev/null es para ocultar el siguiente mensaje de error (known bug):
# Warning: Failed to create directory '/var/www/.wp-cli/cache/': mkdir(): Permission denied.
sudo rm ${WP_DOCROOT}/index.html || true

sudo -u www-data wp core download \
	--locale=es_AR \
	--path="$WP_DOCROOT" 2>/dev/null

# 12. WP-CLI: Crear y personalizar el archivo 'wp-config' de WordPress
sudo -u www-data wp core config \
	--dbname="$DB_NAME" \
	--dbuser="$DB_USER" \
	--dbpass="$DB_PASS" \
	--dbhost="$DB_HOST" \
	--dbprefix='wp_' \
	--path="$WP_DOCROOT"

# 13. WP-CLI: Instalar WordPress
sudo -u www-data wp core install \
	--url="$WEBSERVER_IP" \
	--title='Genesis WordPress' \
	--admin_user="$ADMIN_USER" \
	--admin_password="$ADMIN_PASS" \
	--admin_email="$ADMIN_EMAIL" \
	--path="$WP_DOCROOT" \
	--skip-email

# 14. WP-CLI: Agregar 5 entradas de ejemplo

# Crear entradas y asignar imágenes destacadas
for i in {1..5}; do
  IMG="${WP_DOCROOT}/sample${i}.jpg"
  sudo -u www-data wget -q --timeout=10 -O "$IMG" "https://picsum.photos/800/600?random=${i}"

  POST_ID=$(sudo -u www-data wp post create \
    --post_title="Entrada Demo $i" \
    --post_content="Esta es la entrada demo número $i, provisionada automáticamente." \
    --post_status=publish \
    --path="$WP_DOCROOT" --porcelain)

  sudo -u www-data wp media import "$IMG" \
    --title="Imagen de ejemplo $i" \
    --post_id=$POST_ID \
    --featured_image \
    --path="$WP_DOCROOT"
done

# 15. WP-CLI: Agregar páginas de ejemplo

# Crear página "Nosotros"
sudo -u www-data wp post create \
  --post_type=page \
  --post_title="Nosotros" \
  --post_content="Esta es una página de ejemplo Nosotros, provisionada automáticamente. Puede editarla luego para agregar contenido real" \
  --post_status=publish \
  --path="$WP_DOCROOT"

# Crear página "Contacto"
sudo -u www-data wp post create \
  --post_type=page \
  --post_title="Contacto" \
  --post_content="Esta es una página de ejemplo Contacto. Agregue su información de contacto aquí." \
  --post_status=publish \
  --path="$WP_DOCROOT"

# Crear página "Servicios"
sudo -u www-data wp post create \
  --post_type=page \
  --post_title="Servicios" \
  --post_content="Esta es una página de ejemplo Servicios. Liste sus servicios aquí." \
  --post_status=publish \
  --path="$WP_DOCROOT"

# 17. Mensaje de instalación exitosa
echo -e "\n======================================================================"
echo "¡El stack LAMP y WordPress se han instalado con éxito!"
echo -e "======================================================================\n"
