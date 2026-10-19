# PHP 8.1 with Apache for CodeIgniter 3 Legacy Portal
FROM php:8.1-apache

# Install required PHP extensions (mysqli, curl, pdo, pdo_mysql)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    && docker-php-ext-install mysqli pdo pdo_mysql curl \
    && a2enmod rewrite \
    && rm -rf /var/lib/apt/lists/*

# Copy CodeIgniter 3 Portal
COPY php_portal/ /var/www/html/

# Set working permissions
RUN chown -R www-data:www-data /var/www/html/ \
    && chmod -R 755 /var/www/html/

EXPOSE 80

CMD ["apache2-foreground"]
