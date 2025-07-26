# Use the official PHP 8.2 FPM image
FROM php:8.2-fpm-alpine

# Install system dependencies and PHP extensions
RUN apk add --no-cache \
    nginx \
    git \
    curl \
    supervisor \
    libzip-dev \
    libpng-dev \
    libjpeg-turbo-dev \
    freetype-dev \
    icu-dev \
    # For gRPC PHP plugin compilation
    autoconf \
    g++ \
    make \
    # Install gRPC PHP extension (crucial for communication with FastAPI)
    && pecl install grpc \
    && docker-php-ext-enable grpc \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j$(nproc) gd pdo_mysql pdo_pgsql zip bcmath opcache intl

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html

COPY . /var/www/html

# Install Composer dependencies
RUN composer install --no-dev --optimize-autoloader

# --- Install protoc and generate PHP gRPC client classes ---
# Install Protocol Buffers compiler (protoc)
RUN apk add --no-cache protobuf

# Download and install grpc_php_plugin
# Check https://github.com/grpc/grpc/releases for the latest version and adjust URL
ENV GRPC_VERSION 1.57.0
RUN curl -LO https://github.com/grpc/grpc/releases/download/v${GRPC_VERSION}/grpc_php_plugin-v${GRPC_VERSION}-linux-x64.tgz \
    && tar -xzf grpc_php_plugin-v${GRPC_VERSION}-linux-x64.tgz \
    && mv grpc_php_plugin /usr/local/bin/ \
    && chmod +x /usr/local/bin/grpc_php_plugin \
    && rm grpc_php_plugin-v${GRPC_VERSION}-linux-x64.tgz

# Generate PHP gRPC client classes from .proto definition
# Ensure your .proto file (e.g., crawler.proto) is in laravel_api/proto
RUN protoc --proto_path=/var/www/html/proto \
           --php_out=/var/www/html/app/Grpc \
           --grpc_out=/var/www/html/app/Grpc \
           --plugin=protoc-gen-grpc=/usr/local/bin/grpc_php_plugin \
           /var/www/html/proto/crawler.proto

# Generate APP_KEY automatically
RUN php artisan key:generate --force

# Copy Nginx configuration
COPY docker/nginx.conf /etc/nginx/http.d/default.conf

# Copy Supervisor configuration
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Set permissions for Laravel
RUN chown -R www-data:www-data storage bootstrap/cache \
    && chmod -R 775 storage bootstrap/cache

EXPOSE 80

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
