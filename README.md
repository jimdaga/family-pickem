# Family Pickem

A comprehensive NFL pick'em league web application built with Django. Compete with friends and family by predicting NFL game winners throughout the season.

## 🏈 Features

### Core Functionality
- **NFL Pick'em League**: Submit weekly picks for NFL games
- **Real-time Scoring**: Automatic game updates and score calculations
- **Multi-Season Support**: Track performance across multiple NFL seasons
- **Google OAuth Integration**: Secure authentication via Google accounts
- **Responsive Design**: Optimized for desktop and mobile devices

### User Experience
- **Weekly Pick Submission**: Easy-to-use interface for making game predictions
- **Live Standings**: Real-time leaderboard with season rankings
- **Score Tracking**: Detailed weekly and season-long performance metrics
- **Game Schedules**: Up-to-date NFL schedules and results
- **User Profiles**: Customizable profiles with taglines and preferences

### Advanced Statistics
- **Pick Accuracy**: Season and lifetime correct pick percentages
- **Perfect Weeks**: Track weeks with 100% correct picks
- **Missed Picks**: Monitor engagement and participation
- **Team Preferences**: Most and least picked teams analysis
- **Week Winners**: Champions for each week of the season
- **Season Champions**: Overall season winners and historical records

### Administrative Features
- **Automated Updates**: Integration with external NFL data sources
- **Bulk Operations**: Administrative tools for managing seasons and users
- **Data Analytics**: Comprehensive statistics via pickemctl integration
- **Flexible Scoring**: Configurable point systems and tiebreakers

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL
- Django 4.0+
- Google OAuth credentials

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/family-pickem.git
   cd family-pickem
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   cd pickem
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   export SECRET_KEY="your-secret-key"
   export DATABASE_URL="postgresql://user:password@localhost/pickem"
   export GOOGLE_OAUTH2_KEY="your-google-oauth-key"
   export GOOGLE_OAUTH2_SECRET="your-google-oauth-secret"
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start development server**
   ```bash
   python manage.py runserver
   ```

Visit `http://localhost:8000` to access the application.

## 📱 Usage

### For Players

1. **Sign In**: Use Google OAuth to authenticate
2. **Make Picks**: Navigate to the picks page and select winners for upcoming games
3. **View Standings**: Check your ranking on the leaderboard
4. **Track Stats**: Monitor your performance in the statistics section
5. **Check Scores**: Follow live game results and your pick accuracy

### For Administrators

1. **Admin Panel**: Access Django admin at `/admin/`
2. **Manage Users**: Add/remove users and manage permissions
3. **Update Games**: Import NFL schedules and update scores
4. **Monitor Stats**: Use pickemctl for advanced analytics
5. **Season Management**: Configure new seasons and scoring rules

## 🏗️ Project Structure

```
family-pickem/
├── pickem/                     # Main Django project
│   ├── pickem/                 # Project settings
│   │   ├── settings.py         # Django configuration
│   │   ├── urls.py            # Main URL routing
│   │   └── utils.py           # Utility functions
│   ├── pickem_api/            # Core API and models
│   │   ├── models.py          # Database models
│   │   ├── views.py           # API views
│   │   ├── serializers.py     # DRF serializers
│   │   └── admin.py          # Admin configuration
│   ├── pickem_homepage/       # Frontend views and templates
│   │   ├── views.py           # Page views
│   │   ├── forms.py           # Django forms
│   │   ├── templates/         # HTML templates
│   │   ├── static/            # CSS, JS, images
│   │   └── templatetags/      # Custom template tags
│   └── requirements.txt       # Python dependencies
├── pickemctl/                 # Analytics CLI tool
├── charts/                    # Kubernetes Helm charts
├── docker/                    # Docker configuration
└── infra/                     # Infrastructure as code
```

## 🗄️ Database Models

### Core Models

- **`GamesAndScores`**: NFL game data, scores, and metadata
- **`GamePicks`**: User predictions for individual games
- **`userSeasonPoints`**: Season-long point totals and weekly winners
- **`userStats`**: Comprehensive user performance statistics
- **`Teams`**: NFL team information and logos
- **`GameWeeks`**: Week definitions and scheduling
- **`UserProfile`**: Extended user information and preferences

### Key Relationships

```python
# User makes many GamePicks
User → GamePicks (One-to-Many)

# Each GamePick relates to a Game
GamePicks → GamesAndScores (Many-to-One)

# Users have season point records
User → userSeasonPoints (One-to-Many)

# Users have comprehensive statistics
User → userStats (One-to-One)
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `GOOGLE_OAUTH2_KEY` | Google OAuth client ID | Yes |
| `GOOGLE_OAUTH2_SECRET` | Google OAuth client secret | Yes |
| `DEBUG` | Enable debug mode | No |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | No |

### Settings Configuration

Key settings in `settings.py`:

```python
# Google OAuth
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'}
    }
}

# Current season configuration
CURRENT_SEASON = "2425"  # 2024-2025 NFL season

# Database
DATABASES = {
    'default': dj_database_url.parse(os.environ.get('DATABASE_URL'))
}
```

## 🎯 API Endpoints

### Public Endpoints
- `GET /` - Homepage with league overview
- `GET /scores/` - Game scores and results
- `GET /standings/` - Current standings
- `GET /stats/` - Player statistics
- `GET /rules/` - League rules

### Authenticated Endpoints
- `GET/POST /picks/` - Submit and view picks
- `GET /profile/` - User profile management

### Admin API
- `GET /api/games/` - Game data API
- `POST /api/update-scores/` - Score update webhook

## 📊 Statistics Features

The application tracks comprehensive user statistics:

### Performance Metrics
- **Pick Accuracy**: Percentage of correct predictions
- **Weeks Won**: Number of weekly championships
- **Perfect Weeks**: Weeks with 100% accuracy
- **Seasons Won**: Number of season championships
- **Missed Picks**: Games not predicted

### Team Analysis
- **Most Picked Teams**: Favorite teams by user
- **Least Picked Teams**: Avoided teams by user
- **Team Performance**: Success rate by team picked

### Historical Data
- **Season Comparisons**: Year-over-year performance
- **Lifetime Records**: All-time statistics
- **Trend Analysis**: Performance patterns over time

## 🐳 Docker Deployment

### Using Docker Compose

```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/pickem
    depends_on:
      - db
  
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=pickem
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Kubernetes Deployment

Helm charts are provided in the `charts/` directory:

```bash
helm install family-pickem ./charts/family-pickem
```

## 🔧 Development

### Running Tests

```bash
python manage.py test
```

### Code Style

```bash
# Format code
black .

# Lint code
flake8 .

# Sort imports
isort .
```

### Database Operations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Load sample data
python manage.py loaddata fixtures/sample_data.json
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write tests for new features
- Update documentation for API changes
- Use meaningful commit messages
- Keep PRs focused and atomic

## 🛠️ Tools and Technologies

### Backend
- **Django 4.0+**: Web framework
- **Django REST Framework**: API development
- **PostgreSQL**: Primary database
- **Celery**: Background task processing
- **Redis**: Caching and session storage

### Frontend
- **Bootstrap 5**: CSS framework
- **JavaScript (ES6+)**: Dynamic interactions
- **Chart.js**: Statistics visualization
- **Font Awesome**: Icons

### Authentication
- **django-allauth**: Social authentication
- **Google OAuth 2.0**: Primary login method

### DevOps
- **Docker**: Containerization
- **Kubernetes**: Orchestration
- **Helm**: Package management
- **GitHub Actions**: CI/CD pipeline

### Analytics
- **pickemctl**: Custom Go-based analytics tool
- **PostgreSQL**: Advanced queries and statistics

## 📈 Performance

### Optimization Features
- Database query optimization with select_related/prefetch_related
- Redis caching for frequently accessed data
- Static file compression and CDN integration
- Lazy loading for large datasets
- Efficient pagination for standings and statistics

### Monitoring
- Django debug toolbar for development
- Application performance monitoring
- Database query analysis
- Error tracking and logging

## 🔒 Security

### Security Measures
- CSRF protection on all forms
- SQL injection prevention via ORM
- XSS protection with template escaping
- Secure session management
- HTTPS enforcement in production
- Rate limiting on API endpoints

### Authentication Security
- OAuth 2.0 implementation
- Session-based authentication
- Secure password requirements for admin users
- Account lockout protection

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋 Support

### Getting Help
- **Issues**: Report bugs via GitHub Issues
- **Discussions**: Ask questions in GitHub Discussions
- **Documentation**: Check the wiki for detailed guides
- **Email**: Contact maintainers for urgent issues

### Common Issues
- **OAuth Setup**: Ensure Google OAuth credentials are correctly configured
- **Database Connection**: Verify PostgreSQL connection settings
- **Static Files**: Run `collectstatic` for production deployments
- **Migrations**: Always run migrations after updates

## 🚀 Roadmap

### Upcoming Features
- [ ] Mobile app development
- [ ] Real-time notifications
- [ ] Advanced analytics dashboard
- [ ] Multi-league support
- [ ] Playoff bracket predictions
- [ ] Social features and messaging
- [ ] API rate limiting and versioning
- [ ] Enhanced mobile responsive design

### Version History
- **v2.0.0**: Advanced statistics and perfect weeks tracking
- **v1.5.0**: Missed picks tracking and engagement metrics
- **v1.4.0**: Season winner tracking and championships
- **v1.3.0**: Enhanced user statistics and analytics
- **v1.2.0**: Multi-season support
- **v1.1.0**: Real-time scoring updates
- **v1.0.0**: Initial release with core pick'em functionality

---

**Built with ❤️ for family and friends who love NFL football!** 🏈
