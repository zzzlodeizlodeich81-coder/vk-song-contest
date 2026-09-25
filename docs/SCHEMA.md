# Схема данных

## users
vk_id, name

## tracks
id, owner_vk_id, artist, title, lyrics, lyrics_draft, lyrics_confirmed, filename, duration_sec
status: draft | pending | active | rejected

## consents
vk_id, track_id, terms_version, rights_ok, publish_ok, split_ok, accepted_at

## listens
(vk_id, track_id), seconds. Минимум 45 сек для оценки.

## votes
(vk_id, track_id), lyrics/hook/music 1..10. Наружу только суммы.
