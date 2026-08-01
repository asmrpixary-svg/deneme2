# Company Operating System (COS) — XAUUSDT Master

Bu proje, **XAUUSDT (Binance Futures)** sembolüne özel kalibre edilmiş, tamamen modüler, asenkron (`asyncio`) ve kural tabanlı (`rule-based`) bir şirket operasyon sistemidir.

## 🚀 Hızlı Başlangıç (Windows)

Sistemi Windows bilgisayarınızda tek tıkla çalıştırmak için root dizinde yer alan **`run_cos.cmd`** dosyasını çift tıklayarak çalıştırabilirsiniz. Bu komut dosyası şunları yapar:
1. Python yüklü olup olmadığını kontrol eder.
2. Gerekli dosya yollarının varlığını doğrular.
3. Arka planda FastAPI sunucusunu ayağa kaldırır (`http://localhost:8000`).
4. Google Chrome tarayıcınızı açarak otomatik olarak dashboard adresine yönlendirir.

---

## 📈 XAUUSDT Verileri Nereden Çekiliyor?

Sistemin en can alıcı katmanı olan **Market Department (`company/departments/market.py`)**, XAUUSDT canlı verilerini **doğrudan ve münhasıran gerçek zamanlı olarak resmi Binance Vadeli İşlemler (Futures) API** sunucularından çekmektedir.

*   **Kullanılan Gerçek Zamanlı Endpoint:**
    `https://fapi.binance.com/fapi/v1/ticker/price?symbol=XAUUSDT`
*   **Çekim Modeli:** Asenkron `httpx` istemcisi ile her 2 saniyede bir polling yapılarak en son tik fiyatı çekilir ve EventBus'a `Market Updated` olayı olarak yayınlanır.
*   **Hata Toleransı (Fallback):** Binance API'ye erişim sağlanamadığı veya internet koptuğu durumlarda sistem durmaz; son bilinen fiyata bağlı güvenli bir drift simülasyonu ile asenkron akışı sürdürür ve durumu izole loglarında uyarır.

---

## 🛠️ Ana Özellikler & 7 Win-Rate Filtresi

1.  **ConfluenceEvaluator:** Trend, momentum ve EMA hizalamasının aynı anda oluşmasını şart koşar.
2.  **Market Structure:** Fiyat tepelerini/dipleri izleyerek Higher Highs/Higher Lows (HH/HL) ve Lower Highs/Lower Lows (LH/LL) durumlarını algılar.
3.  **Seans/Likidite Filtresi:** Londra ve New York seanslarında aktif çalışırken, düşük likiditeye sahip Asya seansındaki sinyalleri filtreler.
4.  **Haber Penceresi Filtresi:** Makro ekonomik olaylar öncesinde ve sonrasında (T-30/T+30) işlemleri engeller.
5.  **Volatilite Rejim Filtresi:** Ortalama Gerçek Aralık (ATR) belirli bir eşiğin altına indiğinde düşük volatilite rejimi ilan edip sinyalleri durdurur.
6.  **S/R ve Likidite Giriş Onayı:** Önemli destek/direnç seviyelerine çok yakın olan giriş sinyallerini filtreler.
7.  **Ablation & Walk-Forward Doğrulama:** 3 ayrı dönemde bağımsız testler yaparak filtrelerin kümülatif başarısını test eder.
