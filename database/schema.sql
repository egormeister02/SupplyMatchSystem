DROP TABLE IF EXISTS favorites CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS files CASCADE;
DROP TABLE IF EXISTS requests CASCADE;
DROP TABLE IF EXISTS suppliers CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS help_requests CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;


CREATE TABLE IF NOT EXISTS main_categories (
    name VARCHAR(255) NOT NULL UNIQUE PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    main_category_name VARCHAR(255) NOT NULL,

    FOREIGN KEY (main_category_name) REFERENCES main_categories(name)
);

-- Таблица для пользователей
CREATE TABLE IF NOT EXISTS users (
    tg_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW()
);

-- Таблица для поставщиков
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category_id INTEGER,
    description TEXT,
    country VARCHAR(255),
    region VARCHAR(255),
    city VARCHAR(255),
    address VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(255) CHECK (status IN ('pending', 'accepted', 'rejected')) DEFAULT 'pending',
    website VARCHAR(255),
    created_by_id INTEGER,
    tarrif VARCHAR(255),

    FOREIGN KEY (created_by_id) REFERENCES users(tg_id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Таблица для запросов
CREATE TABLE IF NOT EXISTS requests (
    id SERIAL PRIMARY KEY,
    category_id INTEGER,
    description TEXT,
    created_by_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) CHECK (status IN ('pending', 'accepted', 'rejected')) DEFAULT 'pending',

    FOREIGN KEY (created_by_id) REFERENCES users(tg_id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Таблица для файлов
CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    s3_path VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    request_id INTEGER,
    supplier_id INTEGER,
    uploaded_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (request_id) REFERENCES requests(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- Таблица для откликов (совпадений)
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    request_id INTEGER REFERENCES requests(id) NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(id) NOT NULL,
    status VARCHAR(50) CHECK (status IN ('pending', 'accepted', 'rejected')) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица для избранных поставщиков
CREATE TABLE IF NOT EXISTS favorites (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    supplier_id INTEGER,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id, supplier_id),

    FOREIGN KEY (user_id) REFERENCES users(tg_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS help_requests (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    request TEXT NOT NULL,
    status VARCHAR(50) CHECK (status IN ('pending', 'answered', 'closed')) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (user_id) REFERENCES users(tg_id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    match_id INTEGER,
    author_id BIGINT,
    review_id BIGINT,
    review TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (match_id) REFERENCES matches(id),
    FOREIGN KEY (author_id) REFERENCES users(tg_id),
    FOREIGN KEY (review_id) REFERENCES users(tg_id)
);
