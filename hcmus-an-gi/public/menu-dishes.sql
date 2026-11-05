-- Tuy chon: backend tu tao 2 bang nay khi khoi dong. Chay tay neu muon.
CREATE TABLE IF NOT EXISTS place_dishes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  place_id INT NOT NULL,
  name VARCHAR(180) NOT NULL,
  category VARCHAR(120) NULL,
  price BIGINT NULL,
  note VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_dishes_place (place_id)
);
CREATE TABLE IF NOT EXISTS place_menu_meta (
  place_id INT PRIMARY KEY,
  phone VARCHAR(60) NULL,
  hours VARCHAR(255) NULL,
  notes TEXT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
