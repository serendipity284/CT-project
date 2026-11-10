USE hcmus_an_gi;
-- ============================================================
-- HEANA - Hidden Eatery & Alley Navigation Assistant
-- Full Schema (MySQL 8+) - Compliant with Problem Specification
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 1. Users
-- ----------------------------
CREATE TABLE IF NOT EXISTS users (
  id            VARCHAR(64) PRIMARY KEY,
  email         VARCHAR(255) NOT NULL UNIQUE,
  name          VARCHAR(120) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 2. User Preferences (Onboarding Survey - Spec 1.1)
-- ----------------------------
CREATE TABLE IF NOT EXISTS user_preferences (
  user_id       VARCHAR(64) PRIMARY KEY,
  -- Trọng số cá nhân hóa (tổng nên ≈ 1.0, nhưng không bắt buộc)
  w_price       FLOAT NOT NULL DEFAULT 0.30 COMMENT 'Mức độ quan tâm về giá',
  w_distance    FLOAT NOT NULL DEFAULT 0.30 COMMENT 'Mức độ quan tâm về khoảng cách',
  w_quality     FLOAT NOT NULL DEFAULT 0.30 COMMENT 'Mức độ quan tâm về chất lượng/rating',
  w_freshness   FLOAT NOT NULL DEFAULT 0.10 COMMENT 'Mức độ quan tâm về độ mới của thông tin',
  -- Danh sách dị ứng tuyệt đối (JSON array of strings)
  allergies     JSON NOT NULL DEFAULT ('[]') COMMENT '["lạc","hải sản","hành tây",...]',
  survey_done   TINYINT(1) NOT NULL DEFAULT 0,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_pref_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 3. Places (Eateries)
-- ----------------------------
CREATE TABLE IF NOT EXISTS places (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  google_place_id VARCHAR(128) NULL UNIQUE,
  name            VARCHAR(180) NOT NULL,
  campus          ENUM('q5','lang') NOT NULL,
  address         VARCHAR(255) NOT NULL,
  -- Tọa độ chính của quán (có thể bị GPS Drift)
  lat             DECIMAL(9,6) NOT NULL,
  lng             DECIMAL(9,6) NOT NULL,
  -- Tọa độ Cổng hẻm (Alley Entrance) - quan trọng cho routing 2 chặng
  alley_entrance_lat DECIMAL(9,6) NULL,
  alley_entrance_lng DECIMAL(9,6) NULL,
  -- Giờ mở cửa dạng TIME để filter chính xác
  open_time       TIME NULL,
  close_time      TIME NULL,
  hours_text      VARCHAR(80) NULL COMMENT 'Chuỗi hiển thị: 6:00–14:00',
  price_min       INT NOT NULL DEFAULT 0,
  price_max       INT NOT NULL DEFAULT 0,
  cuisine         VARCHAR(80) NOT NULL DEFAULT '',
  rating_avg      DECIMAL(3,2) NOT NULL DEFAULT 0.00,
  rating_count    INT NOT NULL DEFAULT 0,
  image_url       VARCHAR(500) NULL,
  -- Freshness
  updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  is_active       TINYINT(1) NOT NULL DEFAULT 1,
  INDEX idx_places_campus (campus),
  INDEX idx_places_location (lat, lng),
  INDEX idx_places_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 4. Dishes (Menu chi tiết - cần cho Allergy Filter)
-- ----------------------------
CREATE TABLE IF NOT EXISTS dishes (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  place_id      INT NOT NULL,
  name          VARCHAR(120) NOT NULL,
  price         INT NOT NULL,
  -- Thành phần chính (JSON array) - dùng cho Hard Filter dị ứng
  ingredients   JSON NOT NULL DEFAULT ('[]') COMMENT '["thịt heo","hành","lạc","nước mắm"]',
  description   VARCHAR(300) NULL,
  image_url     VARCHAR(500) NULL,
  is_available  TINYINT(1) NOT NULL DEFAULT 1,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_dishes_place FOREIGN KEY (place_id) REFERENCES places(id) ON DELETE CASCADE,
  INDEX idx_dishes_place (place_id),
  INDEX idx_dishes_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 5. Alley Graph - Nodes (Điểm mốc + Cổng hẻm + Quán)
-- ----------------------------
CREATE TABLE IF NOT EXISTS alley_nodes (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  place_id    INT NULL COMMENT 'NULL nếu là landmark trung gian, có giá trị nếu là eatery node',
  name        VARCHAR(120) NOT NULL COMMENT 'Cổng hẻm 215, Cây me lớn, Quán Cơm tấm Mười...',
  lat         DECIMAL(9,6) NOT NULL,
  lng         DECIMAL(9,6) NOT NULL,
  node_type   ENUM('entrance','landmark','eatery') NOT NULL DEFAULT 'landmark',
  image_url   VARCHAR(500) NULL COMMENT 'Hình ảnh thực tế của điểm mốc',
  description VARCHAR(255) NULL,
  campus      ENUM('q5','lang') NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_node_place FOREIGN KEY (place_id) REFERENCES places(id) ON DELETE SET NULL,
  INDEX idx_nodes_type (node_type),
  INDEX idx_nodes_campus (campus)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 6. Alley Graph - Edges (Cạnh nối giữa các node)
-- ----------------------------
CREATE TABLE IF NOT EXISTS alley_edges (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  from_node_id  INT NOT NULL,
  to_node_id    INT NOT NULL,
  distance_m    FLOAT NOT NULL DEFAULT 0 COMMENT 'Khoảng cách mét',
  instruction   VARCHAR(300) NOT NULL COMMENT 'Đi thẳng 40m đến cây me lớn bên trái',
  image_url     VARCHAR(500) NULL,
  is_bidirectional TINYINT(1) NOT NULL DEFAULT 1,
  CONSTRAINT fk_edge_from FOREIGN KEY (from_node_id) REFERENCES alley_nodes(id) ON DELETE CASCADE,
  CONSTRAINT fk_edge_to   FOREIGN KEY (to_node_id)   REFERENCES alley_nodes(id) ON DELETE CASCADE,
  UNIQUE KEY uk_edge (from_node_id, to_node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 7. Reviews
-- ----------------------------
CREATE TABLE IF NOT EXISTS reviews (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  place_id    INT NOT NULL,
  user_id     VARCHAR(64) NOT NULL,
  rating      TINYINT NOT NULL,
  body        VARCHAR(500) NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_reviews_place FOREIGN KEY (place_id) REFERENCES places(id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_user  FOREIGN KEY (user_id)  REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT chk_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 8. Saves (Quán yêu thích)
-- ----------------------------
CREATE TABLE IF NOT EXISTS saves (
  user_id     VARCHAR(64) NOT NULL,
  place_id    INT NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, place_id),
  CONSTRAINT fk_saves_user  FOREIGN KEY (user_id)  REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_saves_place FOREIGN KEY (place_id) REFERENCES places(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 9. Search History
-- ----------------------------
CREATE TABLE IF NOT EXISTS search_history (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  user_id     VARCHAR(64) NOT NULL,
  campus      ENUM('q5','lang') NULL,
  budget      INT NULL,
  radius_m    INT NULL,
  required_dish VARCHAR(80) NULL,
  query_text  VARCHAR(300) NOT NULL,
  result_count INT DEFAULT 0,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_history_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- SEED DATA mẫu (có thể mở rộng)
-- ============================================================

-- Ví dụ places (giữ tương thích với data cũ)
INSERT INTO places (id, name, campus, address, lat, lng, alley_entrance_lat, alley_entrance_lng, open_time, close_time, hours_text, price_min, price_max, cuisine, rating_avg, rating_count) VALUES
(1, 'Cơm tấm Mười', 'q5', 'Hẻm 215 Nguyễn Văn Cừ, Q.5', 10.763900, 106.681200, 10.763700, 106.681500, '06:00:00', '14:00:00', '6:00–14:00', 30000, 45000, 'Cơm', 4.50, 128),
(2, 'Bún bò cô Ba', 'q5', '48 Trần Phú, Q.5', 10.761400, 106.684100, 10.761400, 106.684100, '06:30:00', '21:00:00', '6:30–21:00', 35000, 50000, 'Bún', 4.30, 89),
(3, 'Phở gà An', 'q5', '102 Trần Hưng Đạo, Q.5', 10.764800, 106.679400, 10.764800, 106.679400, '06:00:00', '22:00:00', '6:00–22:00', 40000, 55000, 'Phở', 4.40, 156),
(4, 'Bánh mì que Út', 'q5', 'Cổng sau Nguyễn Văn Cừ', 10.760600, 106.682800, 10.760600, 106.682800, '06:00:00', '19:00:00', '6:00–19:00', 15000, 25000, 'Bánh mì', 4.20, 67),
(9, 'Cơm gà xối mỡ', 'lang', 'Khu phố 6, Linh Trung', 10.871600, 106.800200, 10.871400, 106.800500, '10:00:00', '21:00:00', '10:00–21:00', 35000, 50000, 'Cơm', 4.60, 203)
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Ví dụ dishes với ingredients
INSERT INTO dishes (place_id, name, price, ingredients) VALUES
(1, 'Cơm tấm sườn bì', 35000, '["cơm","sườn","bì","đồ chua","mỡ hành"]'),
(1, 'Cơm tấm sườn trứng', 40000, '["cơm","sườn","trứng ốp la","đồ chua"]'),
(1, 'Cơm tấm bì chả', 32000, '["cơm","bì","chả","đồ chua"]'),
(2, 'Bún bò Huế', 40000, '["bún","thịt bò","giò heo","chả","mắm ruốc","hành"]'),
(2, 'Bún bò đặc biệt', 50000, '["bún","thịt bò","giò","chả","gân","hành"]'),
(3, 'Phở gà', 45000, '["bánh phở","thịt gà","hành","ngò","gừng"]'),
(3, 'Phở gà đặc biệt', 55000, '["bánh phở","thịt gà","trứng","hành","ngò"]'),
(4, 'Bánh mì que pate', 18000, '["bánh mì","pate","chả","rau"]'),
(4, 'Bánh mì que thịt', 20000, '["bánh mì","thịt nguội","pate","rau"]'),
(9, 'Cơm gà xối mỡ', 40000, '["cơm","gà","mỡ hành","dưa chua"]')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Ví dụ alley nodes (cho quán Cơm tấm Mười)
INSERT INTO alley_nodes (id, place_id, name, lat, lng, node_type, campus, description) VALUES
(1, NULL, 'Cổng hẻm 215 Nguyễn Văn Cừ', 10.763700, 106.681500, 'entrance', 'q5', 'Cổng hẻm chính nhìn từ đường Nguyễn Văn Cừ'),
(2, NULL, 'Cây me lớn bên trái', 10.763780, 106.681380, 'landmark', 'q5', 'Cây me lớn, có ghế đá bên dưới'),
(3, NULL, 'Quán nước mía chị Tư', 10.763850, 106.681290, 'landmark', 'q5', 'Quán nước mía có mái che xanh'),
(4, 1, 'Cơm tấm Mười', 10.763900, 106.681200, 'eatery', 'q5', 'Quán cơm tấm Mười - cuối hẻm bên phải')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Edges
INSERT INTO alley_edges (from_node_id, to_node_id, distance_m, instruction) VALUES
(1, 2, 35, 'Đi thẳng vào hẻm khoảng 35m, đến cây me lớn bên trái'),
(2, 3, 25, 'Tiếp tục đi thẳng 25m, qua quán nước mía chị Tư bên phải'),
(3, 4, 20, 'Đi thêm 20m, quán Cơm tấm Mười nằm bên phải tay')
ON DUPLICATE KEY UPDATE instruction=VALUES(instruction);