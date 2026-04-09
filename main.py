import asyncio
import aiohttp
import json
import re
import urllib.parse
from datetime import datetime, timezone

async def fetch_spotify_playlist_with_dates(playlist_id: str):
    """
    Отдельный тестовый скрипт для парсинга плейлистов Spotify, включая получение 
    даты добавления трека (addedAt) и конвертацию ее в timestamp (Unix ms)
    """
    all_tracks = []
    
    try:
        async with aiohttp.ClientSession() as session:
            # Получаем гостевой токен из встроенного плеера Spotify
            print("1. Получаем токен...")
            async with session.get("https://open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M", headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip, deflate, br"}) as resp:
                html = await resp.text()
            
            m_token = re.search(r'\"accessToken\":\"([^\"]+)\"', html)
            if not m_token:
                raise Exception("Токен не найден")
                
            token = m_token.group(1)
            print(f"Токен получен: {token[:10]}...")
            
            offset = 0
            limit = 100
            sha = "9c53fb83f35c6a177be88bf1b67cb080b853e86b576ed174216faa8f9164fc8f"
            
            print(f"2. Загружаем треки (по 100 шт.)...")
            while True:
                vars_json = json.dumps({
                    "uri": f"spotify:playlist:{playlist_id}",
                    "offset": offset,
                    "limit": limit,
                    "enableWatchFeedEntrypoint": False
                }, separators=(',', ':'))
                exts_json = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": sha}}, separators=(',', ':'))
                
                api_url = f"https://api-partner.spotify.com/pathfinder/v1/query?operationName=fetchPlaylist&variables={urllib.parse.quote(vars_json)}&extensions={urllib.parse.quote(exts_json)}"
                
                async with session.get(api_url, headers={"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip, deflate, br"}) as r:
                    if r.status != 200:
                        break
                    res_data = await r.json()
                    
                items = res_data.get('data', {}).get('playlistV2', {}).get('content', {}).get('items', [])
                if not items:
                    break
                    
                for track_wrapper in items:
                    item_v2 = track_wrapper.get('itemV2', {})
                    if not item_v2:
                        continue
                        
                    t_data = item_v2.get('data', {})
                    if not t_data or t_data.get('__typename') != 'Track':
                        continue
                        
                    # Парсинг даты добавления "2026-03-07T19:59:46Z" => timestamp 1772913586000
                    added_at_iso = track_wrapper.get('addedAt', {}).get('isoString')
                    added_at_ts = None
                    if added_at_iso:
                        try:
                            # Заменяем Z для совместимости с fromisoformat 
                            dt = datetime.fromisoformat(added_at_iso.replace('Z', '+00:00'))
                            added_at_ts = int(dt.timestamp() * 1000)
                        except Exception:
                            pass
                            
                    t_id = t_data.get('uri', '').split(':')[-1]
                    title = t_data.get('name', '')
                    artists = [a.get('profile', {}).get('name', '') for a in t_data.get('artists', {}).get('items', [])]
                    
                    cover_url = ""
                    try:
                        cover_url = t_data.get('albumOfTrack', {}).get('coverArt', {}).get('sources', [])[0].get('url', '')
                    except Exception:
                        pass
                        
                    duration = t_data.get('playcast', {}).get('durationMs', 0)
                    if not duration and t_data.get('duration'):
                        duration = t_data.get('duration', {}).get('totalMilliseconds', 0)
                    if not duration and t_data.get('trackDuration'):
                        duration = t_data.get('trackDuration', {}).get('totalMilliseconds', 0)
                        
                    all_tracks.append({
                        "id": f"spotify-{t_id}",
                        "title": title,
                        "artist": ", ".join(artists) if artists else "",
                        "thumbnail": cover_url,
                        "url": "",
                        "spotifyId": t_id,
                        "durationMs": duration,
                        "addedAt": added_at_ts
                    })
                    
                offset += limit
                
            print(f"Всего загружено {len(all_tracks)} треков!")
            return all_tracks
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

if __name__ == "__main__":
    playlist = "2lDWG19UZVgXHthaAjN3VN"
    tracks = asyncio.run(fetch_spotify_playlist_with_dates(playlist))
    
    if tracks:
        print(f"\n--- Всего найдено: {len(tracks)} ---")
        for i, track in enumerate(tracks, 1):
            # Конвертируем timestamp обратно в дату для проверки
            date_str = "Неизвестно"
            if track['addedAt']:
                date_str = datetime.fromtimestamp(track['addedAt'] / 1000).strftime('%Y-%m-%d %H:%M')

            print(f"{i}. {track['artist']} - {track['title']}")
            print(f"   📅 Добавлен: {date_str}")
            print(f"   🖼️ Обложка: {track['thumbnail'] if track['thumbnail'] else 'Отсутствует'}")
            print("-" * 30)
    else:
        print("Ошибка или пустой плейлист.")
