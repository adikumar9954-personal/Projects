# Pokemon TCG AI Battle Agent

AI agent for the [Kaggle Pokemon TCG AI Battle](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle) competition.

## Setup

1. **Clone the repo**
   ```
   git clone <repo-url>
   cd PokemonTCG
   ```

2. **Create and activate virtual environment**
   ```
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # Linux/Mac
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

4. **Set up Kaggle API token**

   Create a new API token at https://www.kaggle.com/settings and set it as an environment variable:
   ```
   # Windows (permanent)
   setx KAGGLE_API_TOKEN "your-token-here"

   # Linux/Mac
   export KAGGLE_API_TOKEN="your-token-here"
   ```

5. **Download competition data**
   ```
   python download_data.py
   ```

## Project Structure

```
PokemonTCG/
├── sample_submission/     # Kaggle-provided SDK and sample agent
│   ├── main.py            # Entry point (agent function)
│   ├── deck.csv           # Deck card IDs (60 cards)
│   └── cg/                # Simulator engine (Python + native lib)
│       ├── api.py          # Data classes, search API, card data API
│       ├── game.py         # Battle control (start, select, finish)
│       ├── sim.py          # Native library bindings
│       └── utils.py        # Dict-to-dataclass helpers
├── EN_Card_Data.csv       # English card database
├── requirements.txt
└── README.md
```

## Running a Test Battle

```
python test_battle.py
```
