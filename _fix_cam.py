import requests
base = 'http://localhost:8001'

# Fix cam_front URL - correct RTSP with special chars
url = 'rtsp://class6s:SklHill2025!%@192.168.100.14:554/Streaming/Channels/1501'
r = requests.put(f'{base}/api/cameras/cam_front', json={
    'name': 'Camera lop hoc',
    'url': url
})
print(f'Update: {r.status_code}')

# Start
r = requests.post(f'{base}/api/cameras/cam_front/start')
print(f'Start: {r.status_code} {r.json()}')
