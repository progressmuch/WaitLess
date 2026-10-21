# WaitLess User Guide

## About This Guide

This guide explains how the WaitLess transport tracking system works and how
each type of user interacts with it. It is written for everyday users —
managers, bus drivers and passengers — and does not require any technical
knowledge.

**How to use this guide**

| If you are… | Read |
|---|---|
| A manager responsible for the transport network | [Part 2 — Management](#part-2--management) |
| A bus driver | [Part 3 — Operators](#part-3--operators-drivers) |
| A passenger looking for a bus | [Part 4 — Commuters](#part-4--commuters-passengers) |
| A developer or technical reader | [Part 6 — Technical Reference](#part-6--technical-reference) |

**A note on the system address.** The system is live at
`https://waitless-api-dl75.onrender.com`. If you are reading this as a
passenger you will normally use the mobile app rather than the web address;
the address is here for reference and for troubleshooting.

---

## Part 1 — Understanding the System

### 1.1 What WaitLess Does

WaitLess is a public transport information system. It answers three questions
that matter to the people who use it:

1. **Is a bus running, and where is it right now?**
2. **When will it reach me?**
3. **How much does the trip cost?**

The system works by connecting three groups of people:

- **Managers** build and maintain the transport network — the stops, the
  routes, the buses, the prices and the staff.
- **Drivers** drive the buses and report where they are.
- **Passengers** look up the information they need.

The link between them is the location information the driver's phone sends.
Once that flows, everything else becomes possible.

### 1.2 The Three Groups of Users

| Group | Role name in the system | What they are responsible for |
|---|---|---|
| Managers | `MANAGEMENT` | The whole network: stops, routes, buses, prices, staff accounts and reports |
| Drivers | `OPERATOR` | Driving an assigned bus and reporting its location |
| Passengers | `COMMUTER` | Finding a bus, a time and a price |

Each person has exactly one role. **Nobody can give themselves a higher
role.** When someone registers through the public sign-up, they always become a
passenger. Only a manager can create a driver or manager account. This is
deliberate: it stops anyone from promoting themselves.

### 1.3 How the Pieces Fit Together

Read the flow from the top. Each step depends on the one before it.

```text
STEP 1   Manager creates STOPS
         Named places with GPS coordinates
         "Harare Central" at -17.8252, 31.0335
              |
              v
STEP 2   Manager creates ROUTES
         An ordered list of at least two stops
         "Harare Central" -> "Chitungwiza" -> "Nganzvau"
              |
              v
STEP 3   Manager registers BUSES
         The actual vehicles, and puts them on a route
              |
              v
STEP 4   Manager creates DRIVER accounts
         and ASSIGNS each driver a bus
              |
              v
STEP 5   Driver starts a TRIP and sends LOCATION updates
         Every few seconds, while the bus is moving
              |
              v
STEP 6   Passenger searches a JOURNEY
         Sees the bus, its last position, an arrival estimate and the price
```

**Why this order matters.** Each step builds on the one before it, and the
system refuses to let you skip ahead. A route with no stops cannot be
published. A driver with no assigned bus cannot start a trip. A bus that has
never reported a position cannot produce an arrival estimate. When something
does not work, the cause is almost always that an earlier step is missing.

### 1.4 Key Words Explained

These words appear throughout the guide.

| Word | Plain meaning |
|---|---|
| **Stop** | A named place where a bus picks up or drops off passengers, with its GPS coordinates |
| **Route** | A named, ordered list of stops that a bus follows. Identified by a short code like `HR-CHI` |
| **Bus** | A vehicle with a registration number, a fleet number and a seating capacity |
| **Driver assignment** | The record that links a driver to a bus for a period of time |
| **Trip** | One single journey of one bus along one route, from starting to finishing |
| **Location update** | One report of where the bus is, with the time the position was measured |
| **Freshness** | How old the latest position is. It tells you whether you can trust it |
| **Arrival estimate (ETA)** | How many minutes the bus is expected to take to reach the passenger |
| **Fare** | The price of one specific journey: a route plus a start stop and an end stop |

### 1.5 The Most Important Idea: Freshness

A bus position is only useful if you know how old it is. If the driver's
phone was out of signal for an hour, the last position they sent is not where
the bus is now.

The system measures this and labels every position with a **freshness
status**:

| Status | Means | What to do with it |
|---|---|---|
| `fresh` | Measured within the last 20 minutes | Trust it completely |
| `stale` | 20 to 40 minutes old | The bus may have moved on. Show a warning |
| `very_stale` | Over 40 minutes old | Do not rely on it. The trip may have ended |
| `unknown` | The bus has never sent a position | There is no information at all |

A good passenger app shows the bus on the map for `fresh` and `stale`
positions, and shows a clear "live location unavailable" message for
`very_stale` and `unknown`. It must never show an old position as if it were
current.

---

## Part 2 — Management

Managers own the transport network. This part walks through everything you
need to set up and run the system, in the order you should do it.

### 2.1 Your Responsibilities at a Glance

| Task | Frequency |
|---|---|
| Create and maintain stops | As the network grows |
| Create and maintain routes | As the network grows |
| Register buses and keep them on routes | Ongoing |
| Create driver and manager accounts | When someone joins |
| Assign a bus to a driver | Every shift |
| Set and adjust fares | When prices change |
| Watch the system during service | Daily |
| Review the reports | Weekly or monthly |

### 2.2 Step 1 — Your First Manager Account

There is one unavoidable exception to the rule that only managers create
manager accounts: the very first manager has to be created directly, before
any account exists.

Your technical contact or administrator runs a one-time script for you. Once
that first account exists, you can create every other account yourself from
the app, and you will never need the script again.

**What you receive:** an email address and password. Sign in and change the
password before sharing the account with anyone.

### 2.3 Step 2 — Signing In

Open the system and enter your email address and password. You will be taken
to your dashboard.

**Things to know about being signed in:**

- Your session lasts **30 minutes**. After that you need to sign in again.
  If staff are working long shifts, they may prefer to sign in again each
  time they begin using the system rather than being signed out mid-task.
- The system never signs anyone out by itself for security reasons. If you
  use a shared device, sign out when you finish.

### 2.4 Step 3 — Creating Stops

A stop is a place where passengers board or alight. Everything else in the
system is built on top of stops, so this is where you start.

**To add a stop, you need three things:**

1. **A clear name** — the name passengers will read, such as "Harare
   Central Bus Terminal". Use the name people actually use locally, not an
   internal code.
2. **The latitude** — how far north or south the place is, as a decimal
   number between −90 and 90.
3. **The longitude** — how far east or west the place is, as a decimal number
   between −180 and 180.

**Getting the coordinates right.** The easiest way is to open the stop in any
map application and copy the coordinates from there. Take them from the
**exact point** where the bus stops, not the centre of the town or the
district — a two-kilometre error will visibly shift the bus on the passenger's
map.

**You can edit a stop later** if its name or position changes. You cannot
delete one, because existing routes still point to it. Instead you *deactivate*
it, which hides it from the public listings while keeping it attached to the
routes that used it. A deactivated stop also stops appearing when passengers
search for journeys.

### 2.5 Step 4 — Creating Routes

A route is an ordered list of stops. The order is what makes it a route — it
is how a passenger reads it, from the first stop to the last.

**To create a route, you need:**

1. **A name** — for example "Harare to Chitungwiza".
2. **A code** — a short unique identifier, two to sixty-four characters using
   letters, digits, hyphens or underscores, for example `HR-CHI`. The code is
   what appears on bus signage and in the app, so keep it short. It is
   converted to capital letters automatically.
3. **The stops, in order** — at least two of them.

**A route without its stops is a draft.** If you create a route and leave the
stop list out, it is created but stays unpublished — invisible to passengers
and not usable by drivers. Once you have added its stops you can publish it.

**A route needs at least two stops before it can be published.** The system
refuses to publish a one-stop route, because a route with a single stop does
not go anywhere.

**Two further rules protect passengers from being misled:**

- The same stop cannot appear twice on one route.
- If you give an estimated travel time for each stop, those times must
  **never get smaller** as you move down the list. Leave the travel times out
  entirely if you do not know them yet — the system allows that.

**Changing a route's stops later.** When you need to add, remove or reorder
stops, use the "replace stops" action and supply the complete new list. The
system applies the whole change at once, so the route is never left in a
half-updated state, and the ordering never develops gaps.

### 2.6 Step 5 — Registering Buses

A bus is a vehicle in your fleet. Each one needs:

1. **A registration number** — the number plate, for example `ABC 1234`.
2. **A fleet number** — your own internal identifier, for example `BUS-001`.
   This is what your staff will actually say out loud, so make it short.
3. **A seating capacity** — the number of passengers, from 1 to 1000.
4. **Optionally a route** — the route this bus normally runs. A bus may join
   the fleet before a route is decided.

Both the registration number and the fleet number are unique. If another bus
already uses one, the system tells you so rather than creating a duplicate.

**You can change any of these later**, including moving a bus to a different
route or removing it from its route.

**The fleet list is private to managers.** Passengers do not need to browse
it, and the system keeps it that way.

### 2.7 Step 6 — Creating Staff Accounts

Managers create driver accounts. To do this you need the person's name, email
address, a password and their role.

**Give each person their own account.** Never share one account between two
drivers. Two reasons: the audit trail should show who did what, and if a
driver leaves, you deactivate one account instead of hunting for who used a
shared login.

**Passwords** must be between 8 and 128 characters. A short phrase that the
person can remember is better than a short complicated word.

**The system never displays a password** after it is set, not even to a
manager. If someone forgets theirs, create a new account for them and
deactivate the old one.

**Roles you can assign:**

| Role | Can do |
|---|---|
| `OPERATOR` | Drive an assigned bus, start and end trips, send location updates |
| `MANAGEMENT` | Everything a driver can do, plus the whole network setup and the reports |

### 2.8 Step 7 — Assigning a Bus to a Driver

An assignment is the link between a driver and a bus. A driver cannot start a
trip without one.

**To make an assignment, choose the driver and the bus.** You identify the
driver by their email address, so you do not need to look up an internal
identifier first.

**You cannot make an assignment if:**

- **The driver already has a bus.** Each driver holds one bus at a time. To
  give them a different one, end their current assignment first.
- **The bus already has a driver.** Each bus has one driver at a time. If the
  bus should change hands, end the previous driver's assignment first.

**Ending an assignment does not delete the record.** It closes the assignment
and keeps it as history, so you can always see who drove which bus and when.
This matters for accountability and for working out how often a particular
bus changes hands.

### 2.9 Step 8 — Setting Fares

A fare is the price of one journey. It always names a complete journey: the
**route**, the **starting stop** and the **ending stop**.

**To set a fare, you need:**

1. The route.
2. The stop the journey starts at.
3. The stop the journey ends at.
4. The amount, as a positive number with at most two decimal places, for
   example `1.50`.
5. Optionally a currency code, three letters, `USD` by default.

**Both stops must actually be on that route**, and they must be different
stops. The system checks this, so a fare can never point at a journey that
does not exist.

### 2.10 Changing a Price Without Losing History

**This is the rule to remember: you never edit a price. You publish a new
one.**

When you set a new price for a journey that already has one, the system
automatically closes the old price at the exact moment the new one starts,
and keeps it as history. Nothing is overwritten and nothing is lost.

This means:

- You can always answer "what did this journey cost last month?"
- A dispute about a price can be settled by looking at the history.
- Two prices can never apply to the same journey at the same moment.

To stop a fare applying at all, **deactivate** it rather than editing it.

The only two things you can change on an existing fare are whether it is
active, and the moment it stops applying. If you try to change the amount
directly, the system refuses — that is the protection described above.

### 2.11 Step 9 — Watching the System Live

**See every trip currently running:**

Open the live operations view. You see each running trip with its bus, its
driver, its route and when it started. You can filter it to one route.

**See where a particular bus is:**

Open any running trip to see the most recent position, the time it was
measured, the time the system received it, and the freshness status.

**What to look for while the system is running:**

| What you see | What it means | What to do |
|---|---|---|
| `fresh` | Working normally | Nothing |
| `stale` | The bus has not reported for over 20 minutes | Check whether the trip is still running and whether the driver has signal |
| `very_stale` | Over 40 minutes | The trip may have ended without being closed, or the driver lost connection for a long time |
| `unknown` | No position ever received | The driver may not have started sending updates |

**A trip that was never ended** keeps showing as active. If a driver finishes
a shift and forgets, that trip stays on the live list and its last position
keeps ageing. Watch for these — they are the most common sign of a problem.

### 2.12 Step 10 — Reading the Reports

The reports describe what passengers have been asking for:

| Report | What it tells you |
|---|---|
| **Overview** | How many journey searches have been made in total |
| **Route popularity** | Which routes are searched for most, busiest first |
| **Destination demand** | Which places passengers are travelling to most |
| **Origin and destination** | Which pairs of stops are travelled between most |
| **Demand by time** | How searches spread across the hours of the day |

> **⚠️ These reports are currently empty**
>
> The system does not yet record journey searches, so every figure reads zero
> no matter how many passengers search. The reports are built and working —
> the data collection behind them is the missing piece. See
> [Known limitations](#65-known-limitations).

### 2.13 Common Problems for Managers

| What you see | What it means | What to do |
|---|---|---|
| "Route needs at least two stops before it can be activated" | You are publishing a route with fewer than two stops | Add the stops, then publish |
| "Route code is already in use" | Another route has that code | Choose a different code |
| "Operator already has an active assignment" | That driver still holds another bus | End the previous assignment, then assign |
| "Bus already has an active operator" | Somebody else drives that bus | End their assignment first |
| "Only users with role OPERATOR can be assigned" | That email belongs to a passenger or a manager | Check the person's role |
| "Email address is already registered" | The account already exists | Use the existing account |
| "Origin and destination stops must be different" | Both stops are the same | Choose a different destination |
| "The stops are not both on this route" | A fare names a stop the route does not serve | Check the route's stop list |
| "Amount must be positive" | A zero or negative price | Enter a positive amount |
| The request is rejected with a long validation message | The details you sent do not match what the system expects | Check the highlighted field |

---

## Part 3 — Operators (Drivers)

Drivers are the people who keep the system alive. Everything passengers see
depends on the location updates a driver sends.

### 3.1 Your Responsibilities

1. Check which bus you have been assigned.
2. Start a trip when you set off.
3. Send your location regularly while driving.
4. End the trip when you finish.

### 3.2 Step 1 — Sign In

Sign in with the email address and password your manager gave you.

### 3.3 Step 2 — Check Your Assignment

**Always do this first.** It tells you which bus you are driving and which
route you are running. You need both before you can start.

If you see "no active assignment", your manager has not given you a bus yet.
Call them and wait — you cannot start a trip without one.

### 3.4 Step 3 — Start Your Trip

Start the trip when you set off. The system needs:

1. **The bus** — from your assignment.
2. **The route** — also from your assignment.

The system then checks a number of things before allowing it:

- The bus and the route must both exist and be in service.
- **The bus must be the one assigned to you.** You cannot start a trip on
  somebody else's bus.
- The bus must not already have a trip running.
- You must not already have a trip running.

If any check fails, the system explains which one, so you can correct it
without guessing.

**Note the trip number the system gives you.** You need it for every location
update.

### 3.5 Step 4 — Send Your Location

This is the heart of the job. Every time you send a location, passengers
closer to you see your bus move on their map, and the arrival estimate
updates.

**What to send:**

| Field | Needed? | What it is |
|---|---|---|
| Latitude and longitude | **Yes** | Where you are |
| Speed | Recommended | How fast you are going, in kilometres per hour. The system uses this to work out arrival times |
| Direction | Optional | Which way you are facing, in degrees from north |
| Time the position was taken | Optional but important | When the phone measured the position, not when the phone sent it |

**How often to send.** Every few seconds while moving is ideal. If your
connection is poor, once every minute is enough to keep the position
`fresh`. If you stop for more than twenty minutes, the position will be
marked `stale` and passengers will be warned.

**Send the time the position was taken, not the time you sent it.** This is
the single most useful thing you can do. If your phone has no signal for ten
minutes and then reconnects, a position stamped with the time it was
actually measured tells the truth. A position stamped with the send time
makes an old position look current, and passengers will be misled.

**A stale position is worse than no position.** If you know the connection is
bad, wait until it is good rather than sending something misleading.

### 3.6 Step 5 — End Your Trip

End the trip when you finish your shift or complete the route. The system
records the finishing time and closes the trip.

**Always end your trip.** A trip left running keeps appearing on the live
operations list and its last position keeps ageing into `very_stale`, which
looks like a fault to managers and to passengers.

### 3.7 Common Problems for Drivers

| What you see | What it means | What to do |
|---|---|---|
| "Operator has no active assignment" | No bus assigned to you | Ask your manager to assign one |
| "Operator is not assigned to this bus" | You selected the wrong bus | Check your assignment and use that bus |
| "Bus already has an active trip" | A previous trip was never ended | End it, then start the new one |
| "Operator already has an active trip" | You started twice | End the earlier trip |
| "Active trip not found" | The trip number is wrong, or it was already ended | Check the live trips list for yours |
| "Operator does not control this trip" | Not your trip | Check the trip number |
| "Latitude must be between -90 and 90" | The phone sent a bad value | Try again; the phone may not have a fix yet |
| "Speed must be between 0 and 200" | The value was out of range | Try again |
| "You are not authenticated" / your session ended | 30 minutes have passed | Sign in again |

---

## Part 4 — Commuters (Passengers)

### 4.1 You Do Not Need an Account

Everything a passenger needs is available without signing in: the network
map, journey searches, arrival estimates and prices. Passengers who want an
account can create one, but it adds nothing they need to travel.

### 4.2 Browsing the Network

You can look at all the stops and all the routes in the system without
signing in. Open a route to see its stops in the order the bus visits them,
with the travel time between stops where that is known.

Only stops and routes that are currently in service are listed. If a stop
has been closed or a route withdrawn, it disappears from these lists rather
than confusing passengers with options that do not run.

### 4.3 Finding Your Bus

A journey search takes two things: **where you are setting off from** and
**where you are going to**. Choose both stops and the system shows you every
route that serves that pair and currently has a bus running on it.

**If the results are empty**, it means no bus is running that route right
now. The route may still exist and may be running later. This is worth
showing clearly to passengers rather than as an error.

### 4.4 Understanding What You See

For each journey the system shows:

| What you see | What it means |
|---|---|
| **The route** | Which route runs your journey, with its name and code |
| **The bus** | The vehicle running it — registration and fleet number, so you can recognise it |
| **The last position** | Where the bus was when it last reported, and the time of that report |
| **The freshness status** | How much to trust that position (see [1.5](#15-the-most-important-idea-freshness)) |
| **The arrival estimate** | Roughly how many minutes until the bus reaches your destination |
| **The price** | What the journey costs, or "not available" if no fare has been set |

**The arrival estimate is a rough guide, not a promise.** It is worked out
from the straight-line distance between the bus's last known position and
your destination, divided by the bus's speed. It does not follow the route,
so it does not allow for the bus still having to reach your *starting* stop
first, and it cannot account for traffic, road conditions or stops along the
way. Treat it as "about this long" and always show the freshness status
alongside it.

**Always show the freshness status.** A bus position that is forty minutes old
presented as a live location is actively misleading. When the status is
`very_stale` or `unknown`, the app should say so plainly rather than
displaying a marker on the map that is not really there.

### 4.5 Checking the Price

You can check the price of a specific journey without running a search, by
choosing a starting stop and an ending stop.

If no price has been set for that journey, the system returns an empty
result rather than a guess. Show "price not available" — never a wrong
price.

### 4.6 Creating an Account (Optional)

If you want an account, you need a name, an email address and a password of
at least 8 characters.

**Your role is always set to passenger.** There is no option to choose
anything else, and trying to set one is rejected. Driver and manager
accounts are created by management.

---

## Part 5 — A Complete Worked Example

This walks through one full cycle of the system so you can see how the parts
fit together. Follow it in order and the system works.

**Manager, once, to set up the network:**

1. Sign in.
2. Create the stops your route will serve — at least two. Note down their
   names as you go.
3. Create a route, add the stops in the order the bus visits them, and
   publish it.
4. Register a bus and put it on that route.
5. Create a driver's account.
6. Assign the bus to that driver.

**Driver, at the start of a shift:**

7. Sign in.
8. Check your assignment — confirm the bus and the route.
9. Start the trip.
10. Send location updates as you drive, several times a minute.
11. End the trip when you finish.

**Passenger, during the run:**

12. Open the app, choose your start stop and your destination.
13. See the bus, its position, how fresh that position is, the arrival
    estimate and the price.
14. As the bus sends more updates, the position moves and the estimate
    updates.

**Manager, during the run:**

15. Open the live operations view and see the trip running, with the bus, the
    driver and the current position.

---

## Part 6 — Technical Reference

*This part is for developers and technical staff. The rest of the guide does
not need it.*

### 6.1 Addressing the System

| Item | Value |
|---|---|
| Base URL | `https://waitless-api-dl75.onrender.com` |
| API prefix | `/api/v1` |
| Interactive documentation | `https://waitless-api-dl75.onrender.com/docs` |
| Health check | `https://waitless-api-dl75.onrender.com/health` |
| Database | Supabase (managed PostgreSQL) |
| Hosting | Render |

### 6.2 Response Format

Every successful response uses the same shape:

```json
{ "data": { }, "message": "Success" }
```

Every error uses:

```json
{ "detail": "Route not found" }
```

### 6.3 Endpoints by Role

**Public — no token required**

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service is alive |
| GET | `/api/v1/routes` | List active routes |
| GET | `/api/v1/routes/{route_id}` | One route with its ordered stops |
| GET | `/api/v1/stops` | List active stops |
| GET | `/api/v1/fares` | Fares that apply right now |
| GET | `/api/v1/fares/search` | Fare for a start and end stop |
| GET | `/api/v1/trips/active` | Trips currently running |
| GET | `/api/v1/trips/{trip_id}/location/latest` | Last known position |
| GET | `/api/v1/journeys/search` | Journey, arrival estimate and price |
| POST | `/api/v1/auth/register` | Create a passenger account |
| POST | `/api/v1/auth/login` | Get an access token |

**Any signed-in user**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/auth/me` | Own profile |

**Driver only**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/operators/me/assignment` | My bus and route |
| POST | `/api/v1/trips/start` | Start a trip |
| POST | `/api/v1/trips/{trip_id}/location` | Send a position |
| POST | `/api/v1/trips/{trip_id}/end` | End a trip |

**Manager only**

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/users` | Create a driver or manager account |
| POST, PATCH | `/api/v1/stops`, `/api/v1/stops/{stop_id}` | Manage stops |
| POST, PATCH | `/api/v1/routes`, `/api/v1/routes/{route_id}` | Manage routes |
| PUT | `/api/v1/routes/{route_id}/stops` | Replace the ordered stop list |
| GET, POST, PATCH | `/api/v1/buses`, `/api/v1/buses/{bus_id}` | Manage the fleet |
| POST | `/api/v1/operators/{operator_email}/assignments` | Assign a bus |
| DELETE | `/api/v1/operators/{operator_email}/assignments` | End an assignment |
| POST, PATCH | `/api/v1/fares`, `/api/v1/fares/{fare_id}` | Manage prices |
| GET | `/api/v1/analytics/*` | Demand reports |

### 6.4 Status Codes

| Code | Meaning | Usual cause |
|---|---|---|
| 200 | Success | |
| 201 | Created | |
| 400 | Malformed request | |
| 401 | Not signed in | Missing or expired token |
| 403 | Not allowed | Wrong role, or not your trip |
| 404 | Not found | Unknown id, or a route that does not exist |
| 405 | Method not allowed | Attempted to delete a route or fare |
| 409 | Conflict | Duplicate code, double assignment, trip already running |
| 422 | Invalid details | Bad coordinates, fewer than two stops, unexpected field |

### 6.5 Known Limitations

| # | Limitation | Effect | Where |
|---|---|---|---|
| 1 | Journey searches are not recorded | All five reports always read zero | `journey_service.py` |
| 2 | The arrival estimate is a straight-line calculation | It ignores the route, traffic and the distance still to travel to the passenger's stop | `eta_service.py` |
| 3 | A very old position produces no arrival estimate | The bus is still listed, but with no estimate | `journey_service.py` |
| 4 | Journey search does not check stop order or whether the route is in service | A search may offer a journey that runs the wrong way, or on a withdrawn route | `journey_service.py` |
| 5 | Sessions last 30 minutes with no refresh | Users must sign in again | `core/security.py` |
| 6 | There is no list of users | Managers must know an email address to assign a bus | `endpoints/auth.py` |
| 7 | Nothing is ever deleted | Routes, stops, buses and fares are deactivated instead, to preserve history | By design |
| 8 | There is no way to fetch a single fare by id | Read fares through the list or the search | `endpoints/fares.py` |
| 9 | The free hosting tier sleeps after 15 minutes idle | The next request can take 30 to 60 seconds; clients need a long timeout and a loading state | Render |
| 10 | Live positions and running trips are public | Anyone can read them without signing in | `endpoints/trips.py` |

### 6.6 Glossary

| Term | Meaning |
|---|---|
| **Stop** | A named place with GPS coordinates |
| **Route** | An ordered list of two or more stops, identified by a unique code |
| **Bus** | A vehicle with a registration number, fleet number and seat capacity |
| **Assignment** | The link between a driver and a bus, with a start and end time |
| **Trip** | One journey of one bus on one route, from `ACTIVE` to `COMPLETED` |
| **Location** | One position report: where the bus was, when it was measured, when it arrived |
| **Freshness** | How old a position is: `fresh` (≤20 min), `stale` (≤40 min), `very_stale`, `unknown` |
| **ETA** | Estimated minutes until the bus reaches the destination |
| **Fare** | The price of one journey: a route plus an origin and a destination stop |
| **Superseded fare** | An old price, closed off when a new one started, kept as history |
| **Deactivate** | Switch something off without deleting it, so history is preserved |
