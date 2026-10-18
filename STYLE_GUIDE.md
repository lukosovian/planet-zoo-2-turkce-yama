# Planet Zoo 2 Türkçe Yerelleştirme Rehberi

Amaç: Oyun en baştan Türkçe yazılmış gibi okunmalı. Kelimesi kelimesine çeviri yok.

## Hitap
- Oyuncuya **sen** diye hitap edilir: "Habitatını genişlet", "Ziyaretçilerin mutsuz".
- Butonlar emir kipinde ve kısa: Kaydet, İptal, Onayla, Sil, Geri.
- Menü ve sekme adları isim olarak yazılır: Personel Yönetimi, Finans, Araştırma.

## Büyük harf
- Kısa başlık, menü, buton ve nesne adları: oyunun görünümüne uymak için her kelimenin ilk harfi büyük (Bakıcı Kulübesi, Personel Odası).
- Cümleler ve açıklamalar normal Türkçe yazımla.
- Türkçe büyük/küçük harf: i → İ, ı → I. "ISTANBUL" değil "İSTANBUL".

## Değişkenler ve etiketler (DOKUNMA)
- `{Value:int}`, `{Species}`, `{reference}`, `[sentiment=Neutral]`, `[INPUT_ICON:...]`, `<b>`, `<br>`, `<h2>`, `&lt;` aynen kalır.
- Cümle içinde yeri değişebilir, metni ise değişmez (`{Value:float:decimalPlaces=1}` olduğu gibi kalır).
- `[sentiment=...]` seslendirme etiketidir; cümlenin sonunda kalsın.
- Değişkene ek getirmekten kaçın (`{Name}'in` → isme göre yanlış olabilir). Cümleyi ek gerektirmeyecek şekilde kur:
  - "{Name}'s habitat is too small" → "Habitat çok küçük: {Name}" ya da "{Name} için habitat çok küçük"
  - Kaçınılmazsa ünlü uyumundan bağımsız yapı kullan: "{Name} adlı hayvan", "{Species} türü".
- Sayıdan sonra çoğul eki gelmez: "{Value:int} animals" → "{Value:int} hayvan".

## Ses tonu
- Arayüz: net ve kısa. "Lütfen" sadece gerçekten gerekiyorsa.
- İpuçları/açıklamalar: akıcı ve doğal, edilgen yapıyı aşırı kullanma.
- Seslendirme (vo_): karakterin kişiliği korunur, konuşma dili kullanılır. Espriler Türkçede karşılığı olan bir espriyle verilir.
- Ziyaretçi düşünceleri (guest_thought): gündelik, kısa, birinci tekil şahıs ("Acıktım!", "Burası çok kalabalık.").
- Zoopedia: ansiklopedik, doğru zoolojik terimler; hayvanların yaygın Türkçe adları. Bilimsel adlar italik ya da olduğu gibi kalır.

## Adlar
- Hayvan türleri: yaygın Türkçe adı (Kızıl Panda, Boz Ayı, Afrika Fili). Türkçe adı yoksa yaygın kullanılan adı ya da İngilizce adı olduğu gibi kullan.
- Marka, şirket ve oyun içi özel isimler aynen kalır: Frontier, Envalza, Zoopedia, Planet Zoo.
- Ziyaretçi ve hayvanlara verilen kişi adları çevrilmez (araç zaten atlıyor).

## Uzunluk
- Butonlar ve kısa etiketler İngilizcesinden fazla uzamamalı. Gerekirse kısalt: "Yönetim" yerine "Yönet" ya da yaygın kısaltma.

## Terimler
- Onaylı terimler `glossary.json` dosyasında. Bir terimi değiştirmek gerekirse önce orada değiştir.
