CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    major VARCHAR(50),
    year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    credits INTEGER,
    instructor VARCHAR(100)
);

INSERT INTO students (name, email, major, year) VALUES
    ('Alice Johnson', 'alice@university.edu', 'Computer Science', 3),
    ('Bob Smith', 'bob@university.edu', 'Mathematics', 2),
    ('Carol White', 'carol@university.edu', 'Physics', 4),
    ('David Brown', 'david@university.edu', 'Computer Science', 1);

INSERT INTO courses (title, credits, instructor) VALUES
    ('Database Systems', 4, 'Dr. Wilson'),
    ('Algorithms', 3, 'Dr. Martinez'),
    ('Web Development', 3, 'Dr. Anderson');
