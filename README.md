# PickemCTL

A CLI tool for updating analytic data and statistics for the family-pickem.com website.

## Features

- **Unified User Statistics**: Generate all user analytics in one command or individually
- **Pick Statistics**: Calculate correct pick percentages and totals for users
- **Team Preferences**: Track most and least picked teams per user
- **Weeks Won**: Calculate weekly and seasonal wins
- **Daemon Mode**: Continuous data collection and updates
- **Database Upserts**: Automatic create/update operations for user statistics

## Installation

```bash
go build -o pickemctl
```

## Configuration

Copy the example configuration file and update with your settings:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` with your database credentials and preferences.

## Usage

### Main Command

- **All User Statistics**: `./pickemctl userStats` - Runs all analytics (pick stats, most picked, least picked)

### Individual Commands (Backwards Compatible)

- **Pick Statistics**: `./pickemctl pickStats`
- **Most Picked Teams**: `./pickemctl topPicked`
- **Least Picked Teams**: `./pickemctl leastPicked`

### Daemon Mode

Start the daemon for continuous data collection:

```bash
./pickemctl daemon
```

The daemon will:
1. Run all user statistics operations immediately
2. Continue running them at the configured interval (default: 30 seconds)
3. Automatically update or create user statistics records in the database

## Package Structure

The application is organized into these packages:

- **`userStats`**: Unified package containing all user analytics functionality
  - `userStats.go`: Main command that runs all analytics
  - `pickStats.go`: Pick accuracy and weeks won calculations
  - `topPicked.go`: Most picked teams analysis
  - `leastPicked.go`: Least picked teams analysis
- **`daemon`**: Continuous data collection service
- **`internal/db`**: Database connection management
- **`internal/dbUtil`**: Database utilities and user statistics operations

## Database Operations

The tool uses intelligent upsert operations that:
- **Create** new user statistics records if they don't exist
- **Update** existing records with only the fields being modified
- **Preserve** existing data when updating specific statistics

All operations work with the PostgreSQL database defined in the Django `userStats` model.

## Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `database.host` | PostgreSQL host | localhost |
| `database.port` | PostgreSQL port | 5432 |
| `database.user` | Database username | postgres |
| `database.password` | Database password | (none) |
| `database.name` | Database name | pickem |
| `database.sslmode` | SSL mode | disable |
| `app.season.current` | Current NFL season | 2425 |
| `daemon.interval` | Update interval (seconds) | 30 |
