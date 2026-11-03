# Bus travel planner

A Streamlit chat that asks a few questions, remembers the answers with LangChain summary memory, and ranks sample intercity buses against your budget, seat, and timing preferences. The winning route is turned into a day-by-day itinerary.

Schedules in `data/buses.json` are sample data, not live inventory. Sightseeing ideas come only from `data/places.json`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Put your Groq key in `.env`:

```
GROQ_API_KEY=your_key_here
```

The app also accepts the key in the sidebar. Ranking works without a key. Summary memory and the written itinerary use Groq when a key is present (`openai/gpt-oss-120b`). Without a key, the chat keeps a short local note and builds the itinerary directly from the place catalog.

## Run

```powershell
streamlit run app.py
```

The chat asks, one at a time, for:

- cities (a start and end, or up to six cities with the start fixed)
- a start date, or flexible dates
- a bus budget per person
- night sleeper, day seater, or no preference, and AC
- cheapest, fastest, or most comfortable
- pace and interests, then anything to avoid

It reads those answers back, then shows the top route, up to two alternatives, and a morning / afternoon / evening plan. A later message such as "I hate 6 a.m. buses" updates the saved answers and ranks the buses again.

The sidebar shows the running summary and the saved answers. Reset starts a new session. Session files stay in `data/sessions/` on this machine.

## Tests

```powershell
pytest
```

The route tests do not call Groq. They check that a cheaper bus outranks a faster expensive one, that a night-sleeper preference drops a 6 a.m. departure when another bus exists, and that a two-leg connection returns those legs.