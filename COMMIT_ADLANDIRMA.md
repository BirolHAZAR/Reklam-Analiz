# Commit adlandırma tercihi

Kullanıcının 15 Ekim 2026 tarihli talimatı:

- Commit adı `reklamanaliz V1.2.<numara>` biçiminde olmalı.
- Her commit oluşturmadan önce son kullanılan commit adı kullanıcıya hatırlatılmalı ve son noktadan sonraki numara sorulmalı.
- Numara otomatik artırılmamalı veya kullanıcı yerine seçilmemeli.
- Son kullanıcı onayı: TikTok bağlantısında izin ekranının her seferinde görünmesini sağlayan düzeltme için kullanıcı 26 Ekim 2026 tarihinde `14` numarasını belirtti ve canlı yayını onayladı. Son kullanılan commit adı `reklamanaliz V1.2.14`; önceki commit `b8741740` / `reklamanaliz V1.2.13` idi. Bir sonraki commit öncesinde son kullanılan `V1.2.14` hatırlatılarak yeni numara sorulmalı.
- Geçmiş istisnası: Kullanıcı 16 Ekim 2026 tarihinde `6` numarasını birden çok kez seçti; `e97c1f82`, `1543b7a5` ve `36e332cf` commitlerinde `reklamanaliz V1.2.6` başlığı tekrar kullanıldı. Paylaşılmış geçmiş değiştirilmedi.
- Bu talimat gelmeden önce `9e587d6e` teknik adıyla main dalına gönderilmişti: `Split large Meta insights reads and preserve transport retry budget`. Bu teknik commit kullanıcı tarafından belirtilen sürüm adıyla kaydedilmiş gibi gösterilmemeli. Paylaşılmış geçmiş sırf adı değiştirmek için yeniden yazılmamalı.
