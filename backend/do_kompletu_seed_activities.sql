-- DoKompletu - test seed
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE is_active = TRUE) THEN
        RAISE EXCEPTION 'Brak aktywnego użytkownika. Najpierw zarejestruj konto w DoKompletu.';
    END IF;
END $$;

WITH organizer AS (
    SELECT id
    FROM users
    WHERE is_active = TRUE
    ORDER BY created_at ASC
    LIMIT 1
),
seed (
    id, title, description, category, start_at, end_at,
    location_name, address, latitude, longitude,
    min_participants, max_participants, price_type, price_amount
) AS (
    VALUES
    ('11111111-1111-1111-1111-000000000001'::uuid,
     'Wieczorna siatkówka',
     'Luźna gra w siatkówkę dla osób na każdym poziomie.',
     'sport-zespolowy',
     now() + interval '1 hour',
     now() + interval '3 hours',
     'Orlik Rataje',
     'os. Piastowskie, Poznań',
     52.3958, 16.9564, 6, 12, 'FREE', NULL),

    ('11111111-1111-1111-1111-000000000002'::uuid,
     'Piłka nożna 6 vs 6',
     'Szukamy kilku osób do amatorskiego meczu piłki nożnej.',
     'sport-zespolowy',
     now() + interval '3 days',
     now() + interval '3 days 2 hours',
     'Orlik Winogrady',
     'Winogrady, Poznań',
     52.4315, 16.9356, 8, 12, 'PAID', 15.00),

    ('11111111-1111-1111-1111-000000000003'::uuid,
     'Wieczór z planszówkami',
     'Planszówki strategiczne i imprezowe, wybór zależnie od grupy.',
     'gry-planszowe',
     now() + interval '1 day',
     now() + interval '1 day 4 hours',
     'Planszówkowa',
     'ul. Strzelecka, Poznań',
     52.4028, 16.9312, 2, 8, 'FREE', NULL),

    ('11111111-1111-1111-1111-000000000004'::uuid,
     'Sesja RPG dla początkujących',
     'Krótka przygoda fantasy. Nie trzeba znać wcześniej systemu.',
     'rpg',
     now() + interval '5 days',
     now() + interval '5 days 4 hours',
     'Centrum Kultury',
     'ul. Święty Marcin, Poznań',
     52.4060, 16.9185, 3, 6, 'FREE', NULL),

    ('11111111-1111-1111-1111-000000000005'::uuid,
     'Turniej Mario Kart',
     'Towarzyski mini turniej Mario Kart. Sprzęt dostępny na miejscu.',
     'gaming',
     now() + interval '1 day 2 hours',
     now() + interval '1 day 5 hours',
     'Gaming Point',
     'ul. Półwiejska, Poznań',
     52.4016, 16.9283, 4, 10, 'PAID', 10.00),

    ('11111111-1111-1111-1111-000000000006'::uuid,
     'Wspólna nauka przed egzaminem',
     'Spokojna sesja wspólnej nauki i wzajemnej motywacji.',
     'wspolna-nauka',
     now() + interval '6 days',
     now() + interval '6 days 3 hours',
     'Biblioteka Raczyńskich',
     'pl. Wolności, Poznań',
     52.4082, 16.9262, 2, NULL, 'FREE', NULL),

    ('11111111-1111-1111-1111-000000000007'::uuid,
     'Python po godzinach',
     'Wspólne programowanie i rozwiązywanie małych zadań w Pythonie.',
     'technologia',
     now() + interval '30 minutes',
     now() + interval '2 hours 30 minutes',
     'Concordia Design',
     'ul. Zwierzyniecka, Poznań',
     52.4096, 16.9040, 3, 10, 'FREE', NULL),

    ('11111111-1111-1111-1111-000000000008'::uuid,
     'Cybersecurity Meetup',
     'Spotkanie dla osób zainteresowanych cyberbezpieczeństwem i IT.',
     'technologia',
     now() + interval '2 days',
     now() + interval '2 days 3 hours',
     'Poznańskie Centrum Superkomputerowo-Sieciowe',
     'ul. Jana Pawła II, Poznań',
     52.4021, 16.9555, 5, 20, 'FREE', NULL),

    ('11111111-1111-1111-1111-000000000009'::uuid,
     'Wieczór projektów IT',
     'Przynieś własny projekt i popracuj razem z innymi osobami z branży.',
     'technologia',
     now() + interval '15 days',
     now() + interval '15 days 3 hours',
     'Coworking Jeżyce',
     'ul. Dąbrowskiego, Poznań',
     52.4143, 16.9006, 2, 15, 'PAID', 20.00),

    ('11111111-1111-1111-1111-000000000010'::uuid,
     'Jam session',
     'Luźne wspólne granie. Gitara, bas, perkusja i inne instrumenty mile widziane.',
     'muzyka',
     now() + interval '10 days',
     now() + interval '10 days 3 hours',
     'Dom Tramwajarza',
     'ul. Słowackiego, Poznań',
     52.4149, 16.9024, 4, 12, 'FREE', NULL),

    ('11111111-1111-1111-1111-000000000011'::uuid,
     'Szkicowanie przy kawie',
     'Spotkanie dla osób, które chcą wspólnie rysować i wymieniać się pomysłami.',
     'kreatywne',
     now() + interval '20 days',
     now() + interval '20 days 2 hours',
     'Kawiarnia Stare Miasto',
     'Stary Rynek, Poznań',
     52.4084, 16.9342, 2, 8, 'PAID', 12.00)
)
INSERT INTO activities (
    id, organizer_id, title, description, category,
    start_at, end_at, location_name, address, location,
    min_participants, max_participants,
    price_type, price_amount, created_at, updated_at
)
SELECT
    seed.id,
    organizer.id,
    seed.title,
    seed.description,
    seed.category,
    seed.start_at,
    seed.end_at,
    seed.location_name,
    seed.address,
    ST_SetSRID(ST_MakePoint(seed.longitude, seed.latitude), 4326)::geography,
    seed.min_participants,
    seed.max_participants,
    seed.price_type,
    seed.price_amount,
    now(),
    now()
FROM seed
CROSS JOIN organizer
ON CONFLICT (id) DO NOTHING;

SELECT
    category,
    COUNT(*) AS activity_count
FROM activities
WHERE end_at >= now()
GROUP BY category
ORDER BY category;
