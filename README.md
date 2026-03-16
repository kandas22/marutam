# ITBP RTC Grain Shop Management System

A comprehensive ration management system for Indo-Tibetan Border Police (ITBP) Recruit Training Centre.

## 🌾 Overview

This system manages the distribution of rations from contractors to grain shops and mess units. It includes:

- **User Management**: Admin-controlled user creation and management
- **Contractor Management**: Track contractors and their supplies
- **Inventory Management**: Grain shop and mess inventory tracking
- **Distribution Tracking**: Log distributions from grain shop to mess
- **Approval Workflow**: Mess updates require admin approval
- **Analytics & Reports**: Daily data flow monitoring

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Streamlit     │────▶│    Flask API    │────▶│    Supabase     │
│   Frontend      │     │    Backend      │     │   PostgreSQL    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## 👥 User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full access - manage users, contractors, mess, items, approvals, view all reports |
| **Grain Shop User** | Manage grain shop inventory, create distributions, view contractors |
| **Mess User** | Manage mess inventory and daily usage (requires approval) |

## 📁 Project Structure

```
marutam/
├── api/                          # Flask Backend
│   ├── app.py                    # Main Flask application
│   ├── database.py               # Supabase connection
│   ├── utils.py                  # Utility functions & decorators
│   └── routes/                   # API Routes
│       ├── auth.py               # Authentication
│       ├── users.py              # User management
│       ├── contractors.py        # Contractor management
│       ├── items.py              # Ration items
│       ├── mess.py               # Mess & daily usage
│       ├── grain_shop.py         # Grain shop inventory
│       ├── distribution.py       # Distribution logs
│       ├── approvals.py          # Approval workflow
│       └── reports.py            # Reports & analytics
├── frontend/                     # Streamlit Frontend
│   ├── app.py                    # Main Streamlit application
│   └── pages/                    # UI Pages
│       ├── dashboard.py
│       ├── users.py
│       ├── contractors.py
│       ├── items.py
│       ├── mess_management.py
│       ├── grain_shop.py
│       ├── distribution.py
│       ├── approvals.py
│       ├── reports.py
│       ├── mess_inventory.py
│       └── daily_usage.py
├── database/
│   └── schema.sql                # PostgreSQL schema
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
└── README.md
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- Supabase account (https://supabase.com)

### 2. Database Setup

1. Create a new Supabase project
2. Go to SQL Editor in Supabase Dashboard
3. Run the contents of `database/schema.sql`

### 3. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required environment variables:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key
FLASK_SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret
```

### 4. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 5. Run the Application

**Terminal 1 - Start Flask API:**
```bash
python api/app.py
```

**Terminal 2 - Start Streamlit Frontend:**
```bash
streamlit run frontend/app.py
```

### 6. Access the Application

- **Frontend**: http://localhost:8501
- **API**: http://localhost:5001

**Default Admin Login:**
- Email: `admin@itbp.gov.in`
- Password: `admin123`

## 📋 Features

### Admin Features
- ✅ User CRUD (create mess and grain shop users)
- ✅ Contractor management
- ✅ Mess unit management
- ✅ Items/Ration management (veg/non-veg/grocery)
- ✅ View and approve/reject pending updates
- ✅ View all inventory and distributions
- ✅ Analytics and data flow reports

### Grain Shop Features
- ✅ Add inventory from contractors
- ✅ View stock levels
- ✅ Create distributions to mess
- ✅ View contractor information

### Mess Features
- ✅ View assigned mess inventory
- ✅ Record daily ration usage
- ✅ View approval status
- ✅ Track consumption history

## 🔒 Security Features

- JWT-based authentication
- Role-based access control (RBAC)
- Password hashing with bcrypt
- Activity logging for audit trail
- Session management

## 📊 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | User login |
| POST | `/api/auth/logout` | User logout |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/change-password` | Change password |

### Users (Admin only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users` | List all users |
| POST | `/api/users` | Create user |
| PUT | `/api/users/:id` | Update user |
| DELETE | `/api/users/:id` | Deactivate user |

### Items
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/items` | List all items |
| POST | `/api/items` | Create item (Admin) |
| PUT | `/api/items/:id` | Update item (Admin) |

### Grain Shop
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/grain-shop/inventory` | List inventory |
| POST | `/api/grain-shop/inventory` | Add inventory |
| GET | `/api/grain-shop/stock-levels` | Get stock summary |

### Distribution
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/distribution` | List distributions |
| POST | `/api/distribution` | Create distribution |
| POST | `/api/distribution/:id/confirm-receipt` | Confirm receipt |

### Reports (Admin only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/dashboard` | Dashboard stats |
| GET | `/api/reports/data-flow` | Daily data flow |
| GET | `/api/reports/activity-log` | Activity log |

## 🛠️ Development

### Running in Development Mode

```bash
# Flask with debug mode
FLASK_DEBUG=1 python api/app.py

# Streamlit with auto-reload
streamlit run frontend/app.py --server.runOnSave true
```

### Testing API

```bash
# Health check
curl http://localhost:5001/api/health

# Login
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@itbp.gov.in","password":"admin123"}'
```

## 📝 License

This project is developed for ITBP RTC internal use.

## 🤝 Support

For issues or questions, contact the system administrator.

---

**Built with ❤️ for ITBP RTC**
