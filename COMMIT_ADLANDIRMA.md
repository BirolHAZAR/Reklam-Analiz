# Commit adlandırma tercihi

Kullanıcının 15 Ekim 2026 tarihli talimatı:

- Commit adı `reklamanaliz V1.2.<numara>` biçiminde olmalı.
- Her commit oluşturmadan önce son kullanılan commit adı kullanıcıya hatırlatılmalı ve son noktadan sonraki numara sorulmalı.
- Numara otomatik artırılmamalı veya kullanıcı yerine seçilmemeli.
- Son kullanıcı onayı: X Ads reklam hesabı bağlantısı ve gerçek kampanya/reklam metrikleri için `reklamanaliz V1.2.13` (22 Ekim 2026, kullanıcının belirttiği numara: `13`). Bu commit ile son kullanılan ad da `reklamanaliz V1.2.13` olur. Önceki commit ve önceki onaylanan sürüm `reklamanaliz V1.2.12` (`7a538b30`) idi. Bir sonraki commit öncesinde `V1.2.13` hatırlatılarak yeni numara sorulmalı.
- Geçmiş istisnası: Kullanıcı 16 Ekim 2026 tarihinde `6` numarasını birden çok kez seçti; `e97c1f82`, `1543b7a5` ve `36e332cf` commitlerinde `reklamanaliz V1.2.6` başlığı tekrar kullanıldı. Paylaşılmış geçmiş değiştirilmedi.
- Bu talimat gelmeden önce `9e587d6e` teknik adıyla main dalına gönderilmişti: `Split large Meta insights reads and preserve transport retry budget`. Bu teknik commit kullanıcı tarafından belirtilen sürüm adıyla kaydedilmiş gibi gösterilmemeli. Paylaşılmış geçmiş sırf adı değiştirmek için yeniden yazılmamalı.
