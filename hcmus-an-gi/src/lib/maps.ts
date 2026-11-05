/** Địa chỉ lưu trong DB có dạng "địa chỉ | ghi chú". Tách ra để hiển thị và dựng link Google Maps. */
export function splitAddress(raw: string): { address: string; note: string } {
  const i = raw.indexOf(" | ");
  if (i < 0) return { address: raw.trim(), note: "" };
  return { address: raw.slice(0, i).trim(), note: raw.slice(i + 3).trim() };
}

/** Link Google Maps tìm đúng theo địa chỉ đã lưu (không kèm ghi chú). */
export function mapsSearchUrl(rawAddress: string): string {
  const { address } = splitAddress(rawAddress);
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
}

/** Link Google Maps theo tọa độ đã lưu (chính xác nếu quán được định vị bằng link/ghim). */
export function mapsPinUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
}
