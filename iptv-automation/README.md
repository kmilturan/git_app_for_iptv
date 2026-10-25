# IPTV Playlist Automation

Python 3.11+ ilə işləyən, GitHub Actions vasitəsilə saatda bir dəfə yenilənən M3U playlist builder.

## Nələr edir?
- `sources.txt` daxilində göstərilən M3U mənbələrini oxuyur.
- Kanal adlarını mövcud master siyahısı və alias-larla uyğunlaşdırır.
- İcazəsiz/ödənişli xidmət adları üçün mövcud bloklama qaydasını saxlayır.
- URL-lərin əlçatanlığını paralel yoxlayır və təkrar URL yoxlamalarını keşləyir.
- Nəticəni sabit mənbə sırası ilə yaradır və kanal açarlarına görə təkrarları silir.
- Yalnız struktur yoxlaması və minimum kanal sayını keçəndən sonra `playlist.m3u` faylını atomik şəkildə əvəz edir.
- Bütün mənbələr uğursuz olarsa və ya nəticə şübhəli dərəcədə az olarsa, əvvəlki playlist-i saxlayır.

## Vacib məhdudiyyət
HTTP sorğusunun uğurlu olması canlı kanalın pleyerdə mütləq işləyəcəyini zəmanət vermir. Bəzi stream-lər geoblok, token, DRM, referer və ya cookie tələb edə bilər. Bu layihə DRM və ya giriş məhdudiyyətlərini keçməyə çalışmır. Yalnız yayımına baxmaq və paylaşmaq hüququnuz olan mənbələrdən istifadə edin.

## Lokal işə salma
Python 3.11 və ya 3.12 quraşdırın.

```bash
python -m unittest discover -s tests -v
python src/main.py
```

Uğurlu nəticə layihə kökündə `playlist.m3u` faylına yazılır.

## Mənbələrin dəyişdirilməsi
`sources.txt` faylında hər sətirdə bir M3U/M3U8 playlist URL-i yazın. `#` ilə başlayan sətirlər şərh sayılır. Yalnız ictimai və ya istifadəsinə icazəniz olan mənbələrdən istifadə edin.

## GitHub Actions qurulması
1. Bu faylları GitHub repository-yə yükləyin.
2. Repository → **Settings → Actions → General** bölməsinə keçin.
3. Workflow permissions altında **Read and write permissions** seçin.
4. `.github/workflows/update-playlist.yml` workflow-u saatda bir dəfə (UTC üzrə hər saatın 17-ci dəqiqəsində) işləyəcək.
5. İlk dəfə **Actions → Update IPTV playlist → Run workflow** ilə əl ilə başladın.
6. Uğurlu run nəticəsində `playlist.m3u` dəyişibsə, bot commit və push edəcək.

GitHub Actions cron işə düşməsi tam dəqiqə zəmanəti vermir; GitHub yüklənməsinə görə gecikə bilər. Public repository-lərdə schedule davranışı və limitləri GitHub tərəfindən dəyişdirilə bilər.

## Parametrlər
Environment variables:
- `SOURCE_TIMEOUT` — mənbə yükləmə timeout-u (default 15 saniyə)
- `STREAM_TIMEOUT` — hər stream üçün timeout (default 6 saniyə)
- `WORKERS` — paralel işçi sayı (default 16, maksimum 64)
- `RETRIES` — əlavə təkrar cəhd sayı (default 1)
- `MIN_CHANNELS` — playlist-i qəbul etmək üçün minimum kanal sayı (default 5)
- `LOG_LEVEL` — `INFO`, `DEBUG`, `WARNING` və s.

## Qeyd
Kanalın master siyahıda tanınması onun yayımının rəsmi və ya icazəli olması demək deyil. `tvg-id` identifikatorlarını EPG mənbəyinizlə ayrıca yoxlayın.
