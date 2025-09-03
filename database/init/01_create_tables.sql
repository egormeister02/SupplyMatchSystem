-- Create users table
CREATE TABLE users (
    tg_id BIGINT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE jokes (
    id SERIAL PRIMARY KEY,
    topic_id BIGINT NOT NULL,
    joke TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE users_jokes (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    joke_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    reaction VARCHAR(8) NOT NULL CHECK (reaction IN ('like', 'dislike', 'skip')) DEFAULT 'skip',

    CONSTRAINT unique_user_joke UNIQUE (user_id, joke_id),
    FOREIGN KEY (user_id) REFERENCES users(tg_id),
    FOREIGN KEY (joke_id) REFERENCES jokes(id)
);

-- View of users' last topics (per user), including topic text
CREATE OR REPLACE VIEW last_topics AS
SELECT 
    u.tg_id,
    lp.topic_id,
    t.topic
FROM users u
JOIN LATERAL (
    SELECT j.topic_id
    FROM users_jokes uj
    JOIN jokes j ON j.id = uj.joke_id
    WHERE uj.user_id = u.tg_id
    ORDER BY uj.created_at DESC, uj.joke_id DESC
    LIMIT 1
) lp ON true
JOIN topics t ON t.id = lp.topic_id;

-- View of (tg_id, joke_id) pairs for jokes not yet heard by the user,
-- restricted to jokes from the last topic used for that user
CREATE OR REPLACE VIEW user_unheard_jokes AS
SELECT lp.tg_id,
       j.id AS joke_id
FROM last_topics lp
JOIN jokes j ON j.topic_id = lp.topic_id
LEFT JOIN users_jokes uj ON uj.user_id = lp.tg_id AND uj.joke_id = j.id
WHERE uj.joke_id IS NULL;