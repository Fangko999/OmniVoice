export const API_BASE = '/api';

const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
export const WS_BASE = import.meta.env.DEV
  ? 'ws://127.0.0.1:8000/api'
  : `${protocol}//${window.location.host}/api`;

export const VOICES = [
  { id: 'my_yen', name: 'Mỹ Yến', type: 'Nữ, Miền Nam', gender: 'F' },
  { id: 'thanh_dat', name: 'Thành Đạt', type: 'Nam, Miền Nam', gender: 'M' },
  { id: 'diem_trinh', name: 'Diễm Trinh', type: 'Nữ, Miền Nam', gender: 'F' },
  { id: 'hung_thinh', name: 'Hưng Thịnh', type: 'Nam, Miền Nam', gender: 'M' },
  { id: 'mai_linh', name: 'Mai Linh', type: 'Nữ, Miền Bắc', gender: 'F' },
  { id: 'mai_loan', name: 'Mai Loan', type: 'Nữ, Miền Bắc', gender: 'F' },
  { id: 'manh_dung', name: 'Mạnh Dũng', type: 'Nam, Miền Bắc', gender: 'M' },
  { id: 'ngoc_huyen', name: 'Ngọc Huyền', type: 'Nữ, Miền Nam', gender: 'F' },
  { id: 'phat_tai', name: 'Phát Tài', type: 'Nam, Miền Nam', gender: 'M' },
  { id: 'thuc_trinh', name: 'Thục Trinh', type: 'Nữ, Miền Nam', gender: 'F' },
  { id: 'tuan_ngoc', name: 'Tuấn Ngọc', type: 'Nam, Miền Bắc', gender: 'M' },
  { id: 'duc_an', name: 'Đức An', type: 'Nam, Miền Bắc', gender: 'M' },
  { id: 'duc_duy', name: 'Đức Duy', type: 'Nam, Miền Nam', gender: 'M' },
  { id: 'storyvert', name: 'Storyvert', type: 'Nam, Trầm ấm', gender: 'M' }
];

export const ROLES = [
  { id: 'narrator', label: 'Dẫn truyện', color: 'var(--role-narrator)' },
  { id: 'male', label: 'Nam', color: 'var(--role-male)' },
  { id: 'female', label: 'Nữ', color: 'var(--role-female)' }
];

/** localStorage helper có giá trị mặc định */
export const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem(`ov:${key}`);
      return v === null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    localStorage.setItem(`ov:${key}`, JSON.stringify(value));
  }
};

export const errMsg = (e) => e?.response?.data?.detail || e?.message || String(e);
