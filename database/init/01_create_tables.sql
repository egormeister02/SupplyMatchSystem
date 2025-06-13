-- Create main_categories table
CREATE TABLE main_categories (
    name VARCHAR(255) NOT NULL UNIQUE PRIMARY KEY
);

-- Create categories table
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    main_category_name VARCHAR(255) NOT NULL,
    FOREIGN KEY (main_category_name) REFERENCES main_categories(name)
);

-- Create users table
CREATE TABLE users (
    tg_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255) CHECK (username IS NULL OR username LIKE '@%'),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(255) CHECK (phone IS NULL OR LENGTH(phone) >= 10),
    email VARCHAR(255) CHECK (email IS NULL OR email ~* '^[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+[.][A-Za-z]+$'),
    role VARCHAR(255) CHECK (role IN ('user', 'admin')) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create suppliers table
CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category_id INTEGER,
    description TEXT,
    country VARCHAR(255),
    region VARCHAR(255),
    city VARCHAR(255),
    address VARCHAR(255),
    contact_username VARCHAR(255) CHECK (contact_username IS NULL OR contact_username LIKE '@%'),
    contact_phone VARCHAR(255),
    contact_email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(255) CHECK (status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
    rejection_reason TEXT,
    verified_by_id BIGINT,
    created_by_id BIGINT,
    tarrif VARCHAR(255),

    FOREIGN KEY (created_by_id) REFERENCES users(tg_id),
    FOREIGN KEY (verified_by_id) REFERENCES users(tg_id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Create requests table
CREATE TABLE requests (
    id SERIAL PRIMARY KEY,
    category_id INTEGER,
    description TEXT,
    created_by_id BIGINT,
    contact_username VARCHAR(255) CHECK (contact_username IS NULL OR contact_username LIKE '@%'),
    contact_phone VARCHAR(255),
    contact_email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) CHECK (status IN ('pending', 'approved', 'rejected', 'closed')) DEFAULT 'pending',
    rejection_reason TEXT,
    verified_by_id BIGINT,
    FOREIGN KEY (created_by_id) REFERENCES users(tg_id) ON DELETE SET NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (verified_by_id) REFERENCES users(tg_id) ON DELETE SET NULL
);

-- Create files table
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    request_id INTEGER,
    supplier_id INTEGER,
    uploaded_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

-- Create matches table
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    status VARCHAR(50) CHECK (status IN ('pending', 'accepted', 'rejected', 'closed')) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

-- Create favorites table
CREATE TABLE favorites (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    supplier_id INTEGER,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id, supplier_id),
    FOREIGN KEY (user_id) REFERENCES users(tg_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- Create help_requests table
CREATE TABLE help_requests (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    request TEXT NOT NULL,
    answer TEXT,
    admin_id BIGINT,
    status VARCHAR(50) CHECK (status IN ('pending', 'answered')) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(tg_id),
    FOREIGN KEY (admin_id) REFERENCES users(tg_id)
);

-- Create reviews table
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    author_id BIGINT,
    review_id BIGINT,
    mark INTEGER CHECK (mark >= 1 AND mark <= 5),
    review TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (author_id) REFERENCES requests(id),
    FOREIGN KEY (review_id) REFERENCES suppliers(id)
); 