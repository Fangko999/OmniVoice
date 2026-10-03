export const formatTime = (totalSeconds) => {
  if (!totalSeconds || totalSeconds <= 0) return 'Không hợp lệ';
  if (totalSeconds < 60) return `~ ${Math.ceil(totalSeconds)} giây`;
  
  const d = Math.floor(totalSeconds / (3600 * 24));
  const h = Math.floor((totalSeconds % (3600 * 24)) / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = Math.ceil(totalSeconds % 60);
  
  let parts = [];
  if (d > 0) parts.push(`${d} ngày`);
  if (h > 0) parts.push(`${h} giờ`);
  if (m > 0) parts.push(`${m} phút`);
  if (d === 0 && h === 0) parts.push(`${s} giây`);
  
  return `~ ${parts.join(' ')}`;
};
