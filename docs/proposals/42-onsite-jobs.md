# On-site jobs: the client's address, travel time, a technician (#42)

Status: **DECIDED (delegated)**, 2026-10-06: the owner asked to keep building without stopping;
these are Claude's recommendations (decision X11 in [`DECISIONS.md`](../DECISIONS.md)).
Phase 7, third capability. Opens **Home & field services** (beta): cleaning, air conditioning,
electricians, plumbers, pest control.

## The need

An air-conditioning technician's job happens at the client's home. The business needs to know
where, has to leave time to drive between jobs, sends a specific technician, and the client wants
to know when the technician is on the way. Today an appointment happens at the business.

## Model

- **An on-site service** is an appointment service marked `on_site`, with `travel_minutes`
  (the time to get there, 0–240). It keeps everything appointments already have: a technician
  (the staff member), working hours, time off, free times, no double booking.
- **Travel time blocks the technician before the job**: a job from 10:00 with 30 minutes of
  travel takes the technician from 09:30. Free times and the database check both count it, so two
  jobs can never leave too little time to get from one to the next.
- **Client addresses** (`app.client_addresses`): a client can have several (home, office), each
  with street, city, floor/apartment, entry notes ("gate code 1234"). A job keeps the address it
  was booked for (a copy on the session), so editing the address later does not change history.
- **Job status** on the session: scheduled → on the way → in progress → done (or cancelled).
  The assigned technician, or anyone who manages bookings, moves it; "done" checks the client in.
  The client sees "the technician is on the way" in the app.
- **Navigation without a maps contract**: an address opens Waze or Google Maps by link; no
  geocoding or maps API key is needed now. Service areas and route optimization come later.
- **Quotes** move to #44 (quotes, deposits and events): one quotes capability serves both
  on-site jobs and events.

## Industry pack

`on_site` and `travel_minutes` on the pack's default services; the words ("job", "technician")
in the translations (`terms.home_services`).

## Screens

- Business web: on-site toggle and travel time on a service; the client card's addresses; booking
  an on-site job picks the address; the session page shows the address with navigation links and
  the job status.
- Business app: "My jobs" for today: the route of the day in order, call the client, navigate,
  on the way / start / done.
- Client app: booking an on-site service asks for the address (or adds one); the booking shows
  the job's status.

## Slices

1. DB + API: on-site services and travel time, client addresses, booking a job with an address,
   job status, free times with travel, my jobs, tests.
2. Business web: service settings, addresses, booking with an address, the job on the session
   page.
3. Apps: "My jobs" in the business app; the address step and job status in the client app.
4. Home & field services opens (beta) with its pack and a demo.
