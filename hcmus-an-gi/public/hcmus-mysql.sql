-- Schema MySQL 8 cho bản Python + MySQL
-- Demo web dùng localStorage / Postgres; file này để port backend thật.

CREATE TABLE IF NOT EXISTS users (
  id VARCHAR(64) PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS places (
  id INT AUTO_INCREMENT PRIMARY KEY,
  google_place_id VARCHAR(128) NULL UNIQUE,
  name VARCHAR(180) NOT NULL,
  campus ENUM('q5','lang') NOT NULL,
  lat DECIMAL(9,6) NOT NULL,
  lng DECIMAL(9,6) NOT NULL,
  price_min INT NOT NULL,
  price_max INT NOT NULL,
  cuisine VARCHAR(80) NOT NULL,
  address VARCHAR(255) NOT NULL,
  hours VARCHAR(80) NOT NULL,
  rating_avg DECIMAL(2,1) NOT NULL DEFAULT 0,
  rating_count INT NOT NULL DEFAULT 0,
  INDEX idx_places_campus (campus)
);

CREATE TABLE IF NOT EXISTS reviews (
  id INT AUTO_INCREMENT PRIMARY KEY,
  place_id INT NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  rating TINYINT NOT NULL,
  body VARCHAR(500) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_reviews_place FOREIGN KEY (place_id) REFERENCES places(id),
  CONSTRAINT fk_reviews_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT chk_rating CHECK (rating BETWEEN 1 AND 5)
);

CREATE TABLE IF NOT EXISTS saves (
  user_id VARCHAR(64) NOT NULL,
  place_id INT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, place_id),
  CONSTRAINT fk_saves_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_saves_place FOREIGN KEY (place_id) REFERENCES places(id)
);

CREATE TABLE IF NOT EXISTS search_history (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  campus ENUM('q5','lang') NOT NULL,
  budget INT NOT NULL,
  radius_m INT NOT NULL,
  query VARCHAR(300) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_history_user FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Seed mẫu (tuỳ chọn)
INSERT INTO places (name, campus, lat, lng, price_min, price_max, cuisine, address, hours) VALUES
('Cơm tấm Mười', 'q5', 10.763900, 106.681200, 30000, 45000, 'Cơm', 'Hẻm 215 Nguyễn Văn Cừ, Q.5', '6:00–14:00'),
('Bún bò cô Ba', 'q5', 10.761400, 106.684100, 35000, 50000, 'Bún', '48 Trần Phú, Q.5', '6:30–21:00'),
('Phở gà An', 'q5', 10.764800, 106.679400, 40000, 55000, 'Phở', '102 Trần Hưng Đạo, Q.5', '6:00–22:00'),
('Bánh mì que Út', 'q5', 10.760600, 106.682800, 15000, 25000, 'Bánh mì', 'Cổng sau Nguyễn Văn Cừ', '6:00–19:00'),
('Trà sữa Nhà Lá', 'q5', 10.765500, 106.683600, 25000, 45000, 'Nước', '27 Châu Văn Liêm, Q.5', '8:00–22:30'),
('Cơm chay Tịnh', 'q5', 10.759800, 106.680100, 25000, 40000, 'Chay', '88 Nguyễn Chí Thanh, Q.5', '7:00–20:00'),
('Hủ tiếu Nam Vang', 'q5', 10.762200, 106.686200, 35000, 55000, 'Hủ tiếu', '15 Hải Thượng Lãn Ông, Q.5', '6:00–13:30'),
('Xôi mặn Sáu', 'q5', 10.766100, 106.680800, 20000, 35000, 'Xôi', 'Góc Nguyễn Văn Cừ – Trần Bình Trọng', '5:30–11:00'),
('Cơm gà xối mỡ', 'lang', 10.871600, 106.800200, 35000, 50000, 'Cơm', 'Khu phố 6, Linh Trung', '10:00–21:00'),
('Bún thịt nướng Ký', 'lang', 10.868400, 106.802600, 30000, 45000, 'Bún', 'Đường số 6, Làng Đại học', '9:00–21:30'),
('Mì cay Seoul', 'lang', 10.872800, 106.798400, 45000, 75000, 'Mì', 'Tòa dịch vụ Linh Trung', '10:00–22:00'),
('Cà phê sân', 'lang', 10.869100, 106.797200, 20000, 40000, 'Nước', 'Đối diện cổng A', '6:30–22:00'),
('Cơm văn phòng Chị Tư', 'lang', 10.866900, 106.800800, 25000, 40000, 'Cơm', 'Hẻm sau KTX', '10:00–13:30'),
('Bánh tráng trộn', 'lang', 10.873500, 106.801900, 15000, 25000, 'Ăn vặt', 'Chợ Linh Trung', '14:00–21:00'),
('Lẩu thái nhóm', 'lang', 10.867500, 106.804400, 70000, 120000, 'Lẩu', 'Đường vào cổng B', '16:00–23:00'),
('Cháo lòng đêm', 'lang', 10.874200, 106.799100, 30000, 50000, 'Cháo', 'Gần vòng xoay Linh Xuân', '18:00–2:00');
