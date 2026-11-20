import React, { useMemo, useState } from "react";
import { Place } from "../lib/heana-types";

interface PlaceListViewProps {
  places: Place[];
  onSelectPlace: (place: Place) => void;
  onAddNewPlace: () => void;
}

type SortOption = "default" | "price_asc" | "distance_asc" | "rating_desc";

export const PlaceListView: React.FC<PlaceListViewProps> = ({
  places,
  onSelectPlace,
  onAddNewPlace,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortOption>("default");

  // Hàm format giá tiền rút gọn (vd: 35000 -> 35k)
  const formatPriceK = (price?: number) => {
    if (price == null || price <= 0) return "?";
    return `${Math.round(price / 1000)}k`;
  };

  // Lọc theo từ khóa tìm kiếm và sắp xếp danh sách
  const filteredAndSortedPlaces = useMemo(() => {
    const keyword = searchQuery.trim().toLowerCase();

    const filtered = places.filter((place) => {
      if (!keyword) return true;
      const matchName = place.name?.toLowerCase().includes(keyword);
      const matchAddress = place.address?.toLowerCase().includes(keyword);
      const matchDish = place.dishes?.some((d) =>
        d.name.toLowerCase().includes(keyword)
      );
      return Boolean(matchName || matchAddress || matchDish);
    });

    const sorted = [...filtered];
    switch (sortBy) {
      case "price_asc":
        sorted.sort(
          (a, b) => (a.price_min ?? Infinity) - (b.price_min ?? Infinity)
        );
        break;
      case "distance_asc":
        sorted.sort(
          (a, b) => (a.distance_m ?? Infinity) - (b.distance_m ?? Infinity)
        );
        break;
      case "rating_desc":
        // Vẫn chạy tốt khi rating chưa có dữ liệu (mặc định 0)
        sorted.sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0));
        break;
      default:
        break;
    }

    return sorted;
  }, [places, searchQuery, sortBy]);

  return (
    <div className="ds-quan-container">
      {/* Header: Tìm kiếm + Thêm mới quán ăn (theo bản vẽ DSQuan.jpg) */}
      <div className="ds-quan-toolbar">
        <div className="ds-search-box">
          <input
            type="text"
            placeholder="Tìm kiếm tên quán, địa chỉ hoặc món ăn..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="ds-search-input"
          />
          {searchQuery && (
            <button
              type="button"
              className="ds-clear-btn"
              onClick={() => setSearchQuery("")}
              title="Xóa tìm kiếm"
            >
              ✕
            </button>
          )}
        </div>

        <button
          type="button"
          className="ds-add-btn"
          onClick={onAddNewPlace}
        >
          + Thêm mới quán ăn
        </button>
      </div>

      {/* Thanh điều khiển Sắp xếp */}
      <div className="ds-sort-bar">
        <span className="ds-count">
          Hiển thị <strong>{filteredAndSortedPlaces.length}</strong> quán ăn
        </span>
        <div className="ds-sort-controls">
          <label htmlFor="sort-select">Sắp xếp:</label>
          <select
            id="sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="ds-sort-select"
          >
            <option value="default">Mặc định</option>
            <option value="price_asc">Giá thấp → cao</option>
            <option value="distance_asc">Gần nhất</option>
            <option value="rating_desc">Đánh giá cao nhất (★)</option>
          </select>
        </div>
      </div>

      {/* Danh sách thẻ quán ăn 2 cột */}
      <div className="ds-card-list">
        {filteredAndSortedPlaces.length === 0 ? (
          <div className="ds-empty-state">
            Không tìm thấy quán ăn nào phù hợp với "{searchQuery}".
          </div>
        ) : (
          filteredAndSortedPlaces.map((place) => {
            const topDishes = place.dishes?.slice(0, 3) ?? [];
            const priceText =
              place.price_min || place.price_max
                ? `${formatPriceK(place.price_min)} - ${formatPriceK(place.price_max)}`
                : "Đang cập nhật giá";

            return (
              <div
                key={place.id}
                className="ds-place-card"
                onClick={() => onSelectPlace(place)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onSelectPlace(place);
                }}
              >
                {/* Cột Trái: Hình + Tên quán + Giá + Sao + Địa chỉ */}
                <div className="ds-card-left">
                  <div className="ds-thumb">
                    {place.image_url ? (
                      <img src={place.image_url} alt={place.name} />
                    ) : (
                      <div className="ds-thumb-placeholder">🍜</div>
                    )}
                  </div>

                  <div className="ds-info">
                    <h4 className="ds-place-name">{place.name}</h4>
                    <div className="ds-place-price">{priceText}</div>
                    <div className="ds-place-meta">
                      <span className="ds-rating">
                        {place.rating ? `${place.rating} ★` : "Chưa có ★"}
                      </span>
                      <span className="ds-dot">•</span>
                      <span className="ds-address">
                        Địa chỉ: {place.address || "Đang cập nhật"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Cột Phải: 3 món tiêu biểu kèm giá */}
                <div className="ds-card-right">
                  {topDishes.length > 0 ? (
                    <>
                      <ul className="ds-dish-list">
                        {topDishes.map((dish, idx) => (
                          <li key={idx} className="ds-dish-item">
                            <span className="ds-dish-name">{dish.name}</span>
                            <span className="ds-dish-price">
                              {formatPriceK(dish.price)}
                            </span>
                          </li>
                        ))}
                      </ul>
                      {(place.dishes?.length ?? 0) > 3 && (
                        <div className="ds-more-dishes">...</div>
                      )}
                    </>
                  ) : (
                    <div className="ds-no-dishes">
                      Đang cập nhật thực đơn...
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};