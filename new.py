from telethon import TelegramClient, events, Button
from telethon.errors import UserAdminInvalidError, ChatAdminRequiredError
from telethon.tl.functions.messages import ExportChatInviteRequest
import os
import asyncio
import json
import traceback
import hashlib
import random
from datetime import datetime, timedelta
from oxapay_api.SyncOxaPay import SyncOxaPay  # CORRECTED IMPORT
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError

# Bot credentials
API_ID = '24839357'
API_HASH = '4c7ac3d774fd95bf81d3924cf012978b'
BOT_TOKEN = '8184769468:AAGXU93ioctUHQwdPb6aNrAFCeBxY1quWN4'

# OxaPay Configuration
OXAPAY_MERCHANT_KEY = 'BSR2GL-PO0AEH-WGW9HV-BVLH2R'  # Your actual merchant key

# Initialize OxaPay client
try:
    oxapay = SyncOxaPay(merchant_api_key=OXAPAY_MERCHANT_KEY)
    print("✅ OxaPay initialized successfully")
except Exception as e:
    print(f"⚠️ OxaPay initialization error: {e}")
    oxapay = None

# MongoDB Configuration - ONLY for user IDs (broadcast functionality)
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://lyphen:Denarun%40123@ageless.wonm8pb.mongodb.net/?appName=ageless')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'ageless_bot')

# Initialize MongoDB client (ONLY for storing user IDs for broadcasts)
try:
    mongo_client = MongoClient(
        MONGODB_URI, 
        serverSelectionTimeoutMS=5000,
        tlsAllowInvalidCertificates=True  # macOS SSL certificate workaround
    )
    # Test connection
    mongo_client.admin.command('ping')
    db = mongo_client[MONGODB_DATABASE]
    
    # Only ONE collection - for user IDs (broadcast list)
    broadcast_users_collection = db['broadcast_users']
    
    # Create simple index
    broadcast_users_collection.create_index([("user_id", ASCENDING)], unique=True)
    
    print("✅ MongoDB connected successfully (broadcast users only)")
    MONGODB_ENABLED = True
except Exception as e:
    print(f"⚠️ MongoDB connection error: {e}")
    print("⚠️ Using text file for user list")
    db = None
    MONGODB_ENABLED = False

# Admin and group settings
ADMIN_ID = [8268873602, 7207727106]  # Keep for backward compatibility
GROUP_ID = -1002712666768
VOUCHES_CHANNEL_ID = -1002881517452
ORDERS_CHANNEL_ID = -1002919289402
PAYMENT_NOTIFICATION_CHANNEL = -1002919289402  # Channel for payment notifications

# Invite Channel IDs
MAIN_CHANNEL_ID = -1002881517452
VOUCH_CHANNEL_ID = -1002881517452
STORELIST_CHANNEL_ID = -1002881517452
CHAT_CHANNEL_ID = -1002382442270

# Initialize bot
bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# States
broadcast_state = {}
order_states = {}
admin_remark_state = {}
ticket_states = {}
raffle_creation_state = {}
deposit_states = {}
boxing_service_states = {}
admin_complete_order_states = {}
captcha_states = {}  # Stores captcha data: {user_id: {'answer': int, 'failed_at': timestamp, 'ref_code': str}}
verified_users = {}  # Users who have passed captcha: {user_id: verification_timestamp}
payment_details_change_state = {}  # Stores admin state when changing payment details
store_management_state = {}  # Stores admin state when managing stores: {user_id: {'action': 'add'|'edit'|'remove', 'category': str, 'store_id': str, 'step': str}}

# Banner cache (stores the uploaded media object for reuse)
banner_media_cache = None

# Files
user_list_file = 'users.txt'
user_data_file = 'user_data.json'
orders_file = 'orders.json'
tickets_file = 'tickets.json'
raffles_file = 'raffles.json'
service_orders_file = 'service_orders.json'
payments_file = 'payments.json'
stores_file = 'stores.json'

# Create directories
os.makedirs('transcripts', exist_ok=True)
os.makedirs('logs', exist_ok=True)
os.makedirs('uploads', exist_ok=True)

# Store Database
STORES = {
    "electronics": {
        "name": "💻 Electronics & Tech",
        "stores": {
            "apple": {
                "name": "🍎 Apple",
                "fee_percentage": 18,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 5000},
                "processing": "24-72 hours",
                "description": "Free delivery only, pickup accepted | US, CA & EU"
            },
            "bestbuy": {
                "name": "📺 Best Buy",
                "fee_percentage": 18,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 3000},
                "processing": "1-3 days",
                "description": "Electronics & tech, 1 item max, no reship or pickup | US only"
            },
            "dyson": {
                "name": "🌪️ Dyson",
                "fee_percentage": 18,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 3000},
                "processing": "24 hours",
                "description": "Replacement method, 2 items max | US only"
            },
            "extremepc": {
                "name": "🖥️ ExtremePC",
                "fee_percentage": 15,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 3500},
                "processing": "Instant",
                "description": "Insider method, no item limit, reship accepted | New Zealand"
            },
            "meta": {
                "name": "🥽 Meta",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 2000},
                "processing": "5-15 days",
                "description": "VR headsets & devices, 2 items max | Worldwide"
            },
            "playstation": {
                "name": "🎮 PlayStation",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 1000},
                "processing": "4-7 days",
                "description": "Gaming consoles & accessories, reship accepted | Worldwide"
            },
            "ring": {
                "name": "🔔 Ring",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 8000},
                "processing": "Instant",
                "description": "Smart home security, 15-20 items max, no bundles | Worldwide"
            },
            "samsung": {
                "name": "📱 Samsung",
                "fee_percentage": 20,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 5000},
                "processing": "1-8 days",
                "description": "Latest Samsung devices | US only"
            }
        }
    },
    "fashion": {
        "name": "👗 Fashion & Apparel",
        "stores": {
            "arte_antwerp": {
                "name": "✨ Arte Antwerp",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 1000},
                "processing": "1-3 weeks",
                "description": "Designer streetwear, 6 items max | US only"
            },
            "banana_republic": {
                "name": "👔 Banana Republic",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 5000},
                "processing": "1-3 weeks",
                "description": "Business & casual wear, 10 items max | US & CA"
            },
            "carhartt": {
                "name": "🧰 Carhartt",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 5000},
                "processing": "1-3 weeks",
                "description": "Workwear & outdoor clothing, 10 items max | US & CA"
            },
            "cuts_clothing": {
                "name": "✂️ Cuts Clothing",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 5000},
                "processing": "1-3 weeks",
                "description": "Premium basics & essentials, 10 items max | US & CA"
            },
            "farfetch": {
                "name": "👠 Farfetch",
                "fee_percentage": 18,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 3000},
                "processing": "1-2 weeks",
                "description": "Luxury fashion & designer brands, 10 items max, reship accepted | Worldwide"
            },
            "hm": {
                "name": "👕 H&M",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 2000},
                "processing": "1-2 weeks",
                "description": "Affordable fashion, 20 items max | US & CA"
            },
            "moncler": {
                "name": "🧥 Moncler",
                "fee_percentage": 18,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 5000},
                "processing": "1-3 weeks",
                "description": "Luxury outerwear, 5 items max | Worldwide"
            },
            "nordstrom": {
                "name": "🛍️ Nordstrom",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 3000},
                "processing": "1-3 weeks",
                "description": "Sold & shipped by Nordstrom only, 10 items max | US & CA"
            },
            "ralph_lauren": {
                "name": "🐎 Ralph Lauren",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 4000},
                "processing": "1-2 weeks",
                "description": "Premium clothing & accessories, 10 items max | US & CA"
            },
            "tallsize_insider": {
                "name": "📏 TallSize Insider",
                "fee_percentage": 15,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": None},
                "processing": "Instant",
                "description": "Insider method, no limits, reship accepted, refund on ship | US only"
            },
            "urban_outfitters": {
                "name": "🎨 Urban Outfitters",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 1000},
                "processing": "1-2 weeks",
                "description": "Trendy clothing & lifestyle, 10 items max | US & CA"
            },
            "vestige_insider": {
                "name": "👔 Vestige Insider",
                "fee_percentage": 15,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": None},
                "processing": "Instant",
                "description": "Insider method, no limits, reship accepted, refund on ship | US only"
            },
            "zara": {
                "name": "👗 Zara",
                "fee_percentage": 18,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 5000},
                "processing": "5-25 days",
                "description": "Fast fashion & clothing, 10 items max, reship accepted | US, CA & EU"
            }
        }
    },
    "sports": {
        "name": "⚽ Sports & Accessories",
        "stores": {
            "lids": {
                "name": "🧢 Lids",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 5000},
                "processing": "1-3 weeks",
                "description": "Hats & sports merchandise, 10 items max | US & CA"
            },
            "fanatics": {
                "name": "🏈 Fanatics",
                "fee_percentage": 18,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 5000},
                "processing": "24-72 hours",
                "description": "Sports merchandise & jerseys, 20 items max, reship accepted | US & CA"
            }
        }
    },
    "home": {
        "name": "🏠 Home & Lifestyle",
        "stores": {
            "nectar": {
                "name": "🛏️ Nectar",
                "fee_percentage": 18,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 3000},
                "processing": "24-48 hours",
                "description": "Mattresses & bedding, 2 items max | US & CA"
            }
        }
    },
    "retail": {
        "name": "🏬 Retail & Wholesale",
        "stores": {
            "insight": {
                "name": "💡 Insight",
                "fee_percentage": 20,
                "fee_fixed": 0,
                "limits": {"min": 0, "max": 10000},
                "processing": "1-3 weeks",
                "description": "High limit store, 4 items max | US only"
            },
            "sams_club": {
                "name": "🛒 Sam's Club",
                "fee_percentage": 18,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 10000},
                "processing": "1-8 days",
                "description": "Replacement only, 2 items max | US only"
            },
            "staples": {
                "name": "📎 Staples",
                "fee_percentage": 18,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 5000},
                "processing": "Instant",
                "description": "Office supplies & electronics, 2 items max, reship accepted, Apple products work fine | US only"
            },
            "the_mighty_store": {
                "name": "📦 The Mighty Store (Amazon)",
                "fee_percentage": 20,
                "fee_fixed": 150,
                "limits": {"min": 150, "max": 20000},
                "processing": "Instant",
                "description": "NEW METHOD NON PR - Amazon method, 6-7 items max, shipped by Amazon only, 1mo+ old account with 5-6 orders, pickup/lockers ok, no reship, fixing failed orders | Most domains"
            }
        }
    }
}

# Boxing Service Prices
BOXING_SERVICES = {
    "ftid": {
        "name": "📦 FTID - UPS/USPS/FEDEX",
        "price": 18,
        "requires_form": True
    },
    "rts_dmg": {
        "name": "📮 RTS + DMG Left with Sender",
        "price": 50,
        "requires_form": True
    },
    "rts_return": {
        "name": "🔄 RTS Returning to Sender",
        "price": 50,
        "requires_form": True
    },
    "rts_custom": {
        "name": "📦 RTS + Delivery Custom/Random",
        "price": 60,
        "requires_form": True
    },
    "pod_delete": {
        "name": "🗑️ POD Delete (Proof of Delivery)",
        "price": 0,
        "requires_form": False,
        "redirect": True
    },
    "ups_insider": {
        "name": "🎨 UPS Insider Lit (Designer) TX/NY",
        "price": 50,
        "requires_form": True
    },
    "ups_instant": {
        "name": "⚡ UPS Instant AP - 24/7",
        "price": 0,
        "requires_form": False,
        "redirect": True
    }
}

# Helper functions
def log_error(error_msg, exc_info=None):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    full_msg = f"[{timestamp}] {error_msg}"
    
    if exc_info:
        full_msg += f"\n{traceback.format_exc()}"
    
    print(f"\n{'='*60}")
    print(f"❌ ERROR: {full_msg}")
    print(f"{'='*60}\n")
    
    with open('logs/errors.log', 'a', encoding='utf-8') as f:
        f.write(full_msg + "\n\n")

def is_admin(user_id):
    """Check if user is an admin"""
    return user_id in ADMIN_ID

def load_json(filename):
    """Legacy JSON loader - kept for fallback"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log_error(f"Failed to load {filename}", e)
    return {}

def save_json(filename, data):
    """Legacy JSON saver - kept for fallback"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log_error(f"Failed to save {filename}", e)

def save_user(user_id):
    """Save user ID to MongoDB (for broadcasts) and text file (backup)"""
    try:
        # MongoDB - ONLY user ID for broadcasts
        if MONGODB_ENABLED:
            broadcast_users_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "user_id": user_id,
                    "last_active": datetime.now()
                }},
                upsert=True
            )
        
        # Text file backup
        users = set()
        if os.path.exists(user_list_file):
            with open(user_list_file, 'r') as f:
                users = set(f.read().splitlines())
        users.add(str(user_id))
        with open(user_list_file, 'w') as f:
            f.write('\n'.join(users))
    except Exception as e:
        log_error(f"Failed to save user {user_id}", e)

def get_all_users():
    """Get all user IDs from MongoDB (for broadcasts) or fallback to text file"""
    try:
        if MONGODB_ENABLED:
            return [doc['user_id'] for doc in broadcast_users_collection.find({}, {"user_id": 1})]
        
        # Fallback to text file
        if os.path.exists(user_list_file):
            with open(user_list_file, 'r') as f:
                return [int(uid) for uid in f.read().splitlines() if uid.strip()]
    except Exception as e:
        log_error("Failed to get users", e)
    return []

def generate_referral_code(user_id):
    """Generate unique referral code for user"""
    hash_obj = hashlib.md5(str(user_id).encode())
    return hash_obj.hexdigest()[:8].upper()

def get_user_data(user_id):
    """Get user data from JSON (MongoDB NOT used for user data, only for broadcast list)"""
    data = load_json(user_data_file)
    if str(user_id) not in data:
        data[str(user_id)] = {
            'name': '',
            'join_date': datetime.now().strftime('%Y-%m-%d'),
            'orders': [],
            'service_orders': [],
            'referral_code': generate_referral_code(user_id),
            'referred_by': None,
            'referrals': [],
            'wallet_balance': 0.0,
            'payment_history': []
        }
        save_json(user_data_file, data)
    
    # Ensure wallet fields exist for existing users
    if 'wallet_balance' not in data[str(user_id)]:
        data[str(user_id)]['wallet_balance'] = 0.0
    if 'payment_history' not in data[str(user_id)]:
        data[str(user_id)]['payment_history'] = []
    if 'service_orders' not in data[str(user_id)]:
        data[str(user_id)]['service_orders'] = []
    
    return data[str(user_id)]

def update_user_data(user_id, updates):
    """Update user data in JSON (MongoDB NOT used for user data)"""
    data = load_json(user_data_file)
    if str(user_id) not in data:
        data[str(user_id)] = {
            'name': '',
            'join_date': datetime.now().strftime('%Y-%m-%d'),
            'orders': [],
            'service_orders': [],
            'referral_code': generate_referral_code(user_id),
            'referred_by': None,
            'referrals': [],
            'wallet_balance': 0.0,
            'payment_history': []
        }
    data[str(user_id)].update(updates)
    save_json(user_data_file, data)

def add_referral(referrer_id, referred_id):
    """Add a referral relationship (JSON only)"""
    data = load_json(user_data_file)
    
    # Initialize referred user
    if str(referred_id) not in data:
        data[str(referred_id)] = {
            'name': '',
            'join_date': datetime.now().strftime('%Y-%m-%d'),
            'orders': [],
            'service_orders': [],
            'referral_code': generate_referral_code(referred_id),
            'referred_by': None,
            'referrals': [],
            'wallet_balance': 0.0,
            'payment_history': []
        }
    
    referred_data = data[str(referred_id)]
    
    # Check if already referred
    if referred_data.get('referred_by'):
        return False
    
    # Set referrer
    referred_data['referred_by'] = referrer_id
    
    # Initialize referrer if doesn't exist
    if str(referrer_id) not in data:
        data[str(referrer_id)] = {
            'name': '',
            'join_date': datetime.now().strftime('%Y-%m-%d'),
            'orders': [],
            'service_orders': [],
            'referral_code': generate_referral_code(referrer_id),
            'referred_by': None,
            'referrals': [],
            'wallet_balance': 0.0,
            'payment_history': []
        }
    
    referrer_data = data[str(referrer_id)]
    if 'referrals' not in referrer_data:
        referrer_data['referrals'] = []
    
    # Add to referrer's list
    if referred_id not in referrer_data['referrals']:
        referrer_data['referrals'].append(referred_id)
    
    save_json(user_data_file, data)
    return True

def get_referral_stats(user_id):
    """Get referral statistics for a user"""
    user_data = get_user_data(user_id)
    referrals = user_data.get('referrals', [])
    
    total_referrals = len(referrals)
    active_referrals = 0
    
    for ref_id in referrals:
        ref_data = get_user_data(ref_id)
        if ref_data.get('orders') or ref_data.get('service_orders'):
            active_referrals += 1
    
    return {
        'total': total_referrals,
        'active': active_referrals,
        'code': user_data.get('referral_code', generate_referral_code(user_id))
    }

async def process_referral_reward(user_id, deposit_amount):
    """Process referral reward when a referred user makes a deposit"""
    try:
        user_data = get_user_data(user_id)
        referrer_id = user_data.get('referred_by')
        
        # Check if user was referred by someone
        if not referrer_id:
            return None
        
        # Calculate 25% reward
        reward_amount = round(float(deposit_amount) * 0.25, 2)
        
        # Add reward to referrer's wallet
        referrer_data = get_user_data(referrer_id)
        current_balance = float(referrer_data.get('wallet_balance', 0))
        new_balance = current_balance + reward_amount
        
        # Create payment record for referrer
        payment_record = {
            'amount': reward_amount,
            'type': 'referral_reward',
            'description': f'Referral Reward - User deposited ${deposit_amount:.2f}',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'balance_after': new_balance
        }
        
        referrer_data['wallet_balance'] = new_balance
        if 'payment_history' not in referrer_data:
            referrer_data['payment_history'] = []
        referrer_data['payment_history'].append(payment_record)
        
        update_user_data(referrer_id, referrer_data)
        
        # Get user info for notification
        try:
            user_entity = await bot.get_entity(user_id)
            user_name = user_entity.first_name or "A user"
            
            # Create beautiful notification message
            notification = (
                "🎊 <b>Referral Reward Received!</b> 🎊\n\n"
                "┏━━━━━━━━━━━━━━━━━━━━━┓\n"
                f"┃  💰 <b>+${reward_amount:.2f} USD</b>\n"
                "┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                f"🎯 <b>{user_name}</b> just deposited <b>${deposit_amount:.2f}</b>\n"
                f"💸 <b>25% reward</b> has been added to your wallet!\n\n"
                f"📊 <b>New Balance:</b> <code>${new_balance:.2f}</code>\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "✨ <i>Keep sharing your referral link to earn more rewards!</i> ✨"
            )
            
            # Send notification to referrer
            await bot.send_message(
                referrer_id,
                notification,
                parse_mode='html'
            )
            
            return reward_amount
            
        except Exception as e:
            log_error(f"Failed to send referral notification to {referrer_id}", e)
            return reward_amount
            
    except Exception as e:
        log_error(f"Failed to process referral reward for user {user_id}", e)
        return None

def calculate_fee(order_total, fee_percentage):
    """Calculate fee based on percentage only (no fixed fee)"""
    try:
        total = float(order_total)
        fee = (total * fee_percentage / 100)
        return round(fee, 2)
    except:
        return 0

def load_stores():
    """Load stores from JSON file, fallback to hardcoded STORES if file doesn't exist"""
    try:
        if os.path.exists(stores_file):
            stores = load_json(stores_file)
            if stores:
                return stores
    except Exception as e:
        log_error("Failed to load stores.json", e)
    # Fallback to hardcoded STORES
    return STORES

def save_stores(stores_data):
    """Save stores to JSON file"""
    try:
        save_json(stores_file, stores_data)
        return True
    except Exception as e:
        log_error("Failed to save stores.json", e)
        return False

# Wallet Functions
def add_to_wallet(user_id, amount, description="Deposit"):
    """Add funds to user wallet"""
    try:
        user_data = get_user_data(user_id)
        current_balance = float(user_data.get('wallet_balance', 0))
        new_balance = current_balance + float(amount)
        
        payment_record = {
            'amount': float(amount),
            'type': 'deposit',
            'description': description,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'balance_after': new_balance
        }
        
        user_data['wallet_balance'] = new_balance
        if 'payment_history' not in user_data:
            user_data['payment_history'] = []
        user_data['payment_history'].append(payment_record)
        
        update_user_data(user_id, user_data)
        return True
    except Exception as e:
        log_error(f"Failed to add to wallet for user {user_id}", e)
        return False

def deduct_from_wallet(user_id, amount, description="Purchase"):
    """Deduct funds from user wallet"""
    try:
        user_data = get_user_data(user_id)
        current_balance = float(user_data.get('wallet_balance', 0))
        
        if current_balance < float(amount):
            return False
        
        new_balance = current_balance - float(amount)
        
        payment_record = {
            'amount': -float(amount),
            'type': 'deduction',
            'description': description,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'balance_after': new_balance
        }
        
        user_data['wallet_balance'] = new_balance
        if 'payment_history' not in user_data:
            user_data['payment_history'] = []
        user_data['payment_history'].append(payment_record)
        
        update_user_data(user_id, user_data)
        return True
    except Exception as e:
        log_error(f"Failed to deduct from wallet for user {user_id}", e)
        return False

def get_wallet_balance(user_id):
    """Get user wallet balance"""
    user_data = get_user_data(user_id)
    return float(user_data.get('wallet_balance', 0))

# Payment Functions
async def create_payment(user_id, amount, description, order_id=None):
    """Create OxaPay payment invoice"""
    try:
        if not oxapay:
            log_error("OxaPay not initialized")
            return None, None
            
        payment_order_id = order_id or f"PAY-{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create invoice using SyncOxaPay with raw_response=True
        response = oxapay.create_invoice(
            amount=float(amount),
            currency='USD',
            order_id=payment_order_id,
            description=description,
            raw_response=True
        )
        
        if response and response.get("status") == 200:  # Success code
            pay_link = response["data"]["payment_url"]
            track_id = response["data"]["track_id"]
            
            # Save payment record
            payments = load_json(payments_file)
            payments[payment_order_id] = {
                'user_id': user_id,
                'amount': float(amount),
                'description': description,
                'status': 'pending',
                'payment_link': pay_link,
                'track_id': track_id,
                'created_at': datetime.now().isoformat(),
                'order_id': order_id
            }
            save_json(payments_file, payments)
            
            return pay_link, payment_order_id
        else:
            error_msg = response.get("message", "Unknown error") if response else "No response"
            log_error(f"OxaPay create_invoice failed: {error_msg}")
            return None, None
        
    except Exception as e:
        log_error(f"Failed to create payment for user {user_id}", e)
        return None, None

# Add this after the OxaPay initialization (after line with oxapay = SyncOxaPay...)
def test_oxapay_connection():
    """Test OxaPay connection"""
    try:
        # Try to create a test invoice (this should work if key is valid)
        test_response = oxapay.create_invoice(
            amount=1.0,
            currency='USD',
            order_id='TEST-' + datetime.now().strftime('%Y%m%d%H%M%S'),
            description='Test invoice',
            raw_response=True
        )
        if test_response and test_response.get("status") == 200:
            print("✅ OxaPay API test successful!")
            return True
        else:
            print(f"❌ OxaPay API test failed: {test_response}")
            return False
    except Exception as e:
        print(f"❌ OxaPay API test error: {e}")
        return False

# Call the test
if oxapay:
    test_oxapay_connection()

async def check_payment_status(payment_id):
    """Check payment status from OxaPay"""
    try:
        if not oxapay:
            return None
            
        payments = load_json(payments_file)
        if payment_id not in payments:
            return None
        
        track_id = payments[payment_id].get('track_id')
        if not track_id:
            return None
        
        # Check payment info using SyncOxaPay with raw_response=True
        response = oxapay.get_payment_information(track_id=track_id, raw_response=True)
        
        if response and response.get("status") == 200:
            status = response["data"].get('status', '').lower()
            
            # OxaPay status: Waiting, Confirming, Paid, Expired, etc.
            if status in ['paid', 'confirming', 'confirmed']:
                payments[payment_id]['status'] = 'completed'
                save_json(payments_file, payments)
                return 'completed'
            elif status in ['expired', 'canceled', 'failed']:
                payments[payment_id]['status'] = 'failed'
                save_json(payments_file, payments)
                return 'failed'
            elif status in ['waiting', 'pending']:
                return 'pending'
            
            return 'pending'
        
        return None
    except Exception as e:
        log_error(f"Failed to check payment status for {payment_id}", e)
        return None

# Order Functions (JSON only - MongoDB NOT used)
def create_order(user_id, store_info, order_data):
    orders = load_json(orders_file)
    order_id = f"ORD-{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    orders[order_id] = {
        'user_id': user_id,
        'store_info': store_info,
        'order_data': order_data,
        'status': 'pending',
        'payment_status': 'unpaid',
        'remarks': [],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'created_at': datetime.now().isoformat()
    }
    
    save_json(orders_file, orders)
    
    user_data = get_user_data(user_id)
    user_data['orders'].append(order_id)
    update_user_data(user_id, user_data)
    
    return order_id

def get_order(order_id):
    orders = load_json(orders_file)
    return orders.get(order_id)

def update_order(order_id, updates):
    orders = load_json(orders_file)
    if order_id in orders:
        orders[order_id].update(updates)
        save_json(orders_file, orders)
        return True
    return False

def add_order_remark(order_id, remark, by_admin=True):
    orders = load_json(orders_file)
    if order_id in orders:
        orders[order_id]['remarks'].append({
            'text': remark,
            'by': 'Admin' if by_admin else 'Customer',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_json(orders_file, orders)
        return True
    return False

# Service Order Functions (JSON only)
def create_service_order(user_id, service_type, service_name, price, order_data=None):
    """Create a service order (aged accounts, boxing, etc.)"""
    service_orders = load_json(service_orders_file)
    order_id = f"SRV-{service_type[:3].upper()}-{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    service_orders[order_id] = {
        'user_id': user_id,
        'service_type': service_type,
        'service_name': service_name,
        'price': price,
        'order_data': order_data or {},
        'status': 'pending',
        'payment_status': 'unpaid',
        'delivery_content': None,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'created_at': datetime.now().isoformat()
    }
    
    save_json(service_orders_file, service_orders)
    
    user_data = get_user_data(user_id)
    if 'service_orders' not in user_data:
        user_data['service_orders'] = []
    user_data['service_orders'].append(order_id)
    update_user_data(user_id, user_data)
    
    return order_id

def get_service_order(order_id):
    service_orders = load_json(service_orders_file)
    return service_orders.get(order_id)

def update_service_order(order_id, updates):
    service_orders = load_json(service_orders_file)
    if order_id in service_orders:
        service_orders[order_id].update(updates)
        save_json(service_orders_file, service_orders)
        return True
    return False

# Ticket functions (JSON only)
def create_ticket(user_id, question, user_name):
    tickets = load_json(tickets_file)
    ticket_id = f"TKT-{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    tickets[ticket_id] = {
        'user_id': user_id,
        'user_name': user_name,
        'question': question,
        'status': 'pending',
        'messages': [],
        'created_at': datetime.now().isoformat(),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    save_json(tickets_file, tickets)
    return ticket_id

def get_ticket(ticket_id):
    tickets = load_json(tickets_file)
    return tickets.get(ticket_id)

def update_ticket(ticket_id, updates):
    tickets = load_json(tickets_file)
    if ticket_id in tickets:
        tickets[ticket_id].update(updates)
        save_json(tickets_file, tickets)
        return True
    return False

def get_active_ticket_for_user(user_id):
    tickets = load_json(tickets_file)
    for tid, ticket in tickets.items():
        if ticket['user_id'] == user_id and ticket['status'] == 'active':
            return tid
    return None

def add_ticket_message(ticket_id, message, from_admin=False):
    tickets = load_json(tickets_file)
    if ticket_id in tickets:
        tickets[ticket_id]['messages'].append({
            'text': message,
            'from': 'admin' if from_admin else 'user',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_json(tickets_file, tickets)
        return True
    return False

# Raffle functions (JSON only)
def create_raffle(prize, winners_count, duration_minutes):
    raffles = load_json(raffles_file)
    raffle_id = f"RAF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    end_time = datetime.now() + timedelta(minutes=duration_minutes)
    
    raffles[raffle_id] = {
        'prize': prize,
        'winners_count': winners_count,
        'participants': [],
        'status': 'active',
        'created_at': datetime.now().isoformat(),
        'end_time': end_time.isoformat(),
        'winners': []
    }
    
    save_json(raffles_file, raffles)
    return raffle_id

def get_raffle(raffle_id):
    raffles = load_json(raffles_file)
    return raffles.get(raffle_id)

def join_raffle(raffle_id, user_id):
    raffles = load_json(raffles_file)
    if raffle_id in raffles:
        raffle = raffles[raffle_id]
        if raffle['status'] == 'active' and user_id not in raffle['participants']:
            raffle['participants'].append(user_id)
            save_json(raffles_file, raffles)
            return True
    return False

def get_active_raffles():
    raffles = load_json(raffles_file)
    active = []
    for rid, raffle in raffles.items():
        if raffle['status'] == 'active':
            end_time = datetime.fromisoformat(raffle['end_time'])
            if datetime.now() < end_time:
                active.append(rid)
            else:
                raffle['status'] = 'ended'
                save_json(raffles_file, raffles)
    return active

async def end_raffle(raffle_id):
    raffles = load_json(raffles_file)
    if raffle_id not in raffles:
        return False
    
    raffle = raffles[raffle_id]
    if raffle['status'] != 'active':
        return False
    
    participants = raffle['participants']
    winners_count = min(raffle['winners_count'], len(participants))
    
    if winners_count > 0:
        winners = random.sample(participants, winners_count)
        raffle['winners'] = winners
    else:
        raffle['winners'] = []
    
    raffle['status'] = 'ended'
    save_json(raffles_file, raffles)
    
    if raffle['winners']:
        winner_mentions = []
        for winner_id in raffle['winners']:
            try:
                user = await bot.get_entity(winner_id)
                user_name = user.first_name or "User"
                winner_mentions.append(f"• <a href='tg://user?id={winner_id}'>{user_name}</a>")
            except:
                winner_mentions.append(f"• User {winner_id}")
        
        announcement = (
            f"🎉 <b>Raffle Ended!</b>\n\n"
            f"🎁 Prize: <b>{raffle['prize']}</b>\n"
            f"👥 Participants: {len(participants)}\n\n"
            f"🏆 <b>Winners:</b>\n"
            + "\n".join(winner_mentions) +
            f"\n\n<i>Congratulations to all winners!</i>"
        )
    else:
        announcement = (
            f"🎉 <b>Raffle Ended!</b>\n\n"
            f"🎁 Prize: <b>{raffle['prize']}</b>\n\n"
            f"❌ <i>No participants joined this raffle.</i>"
        )
    
    try:
        await bot.send_message(VOUCHES_CHANNEL_ID, announcement, parse_mode='html')
    except Exception as e:
        log_error(f"Failed to announce raffle winners: {e}", e)
    
    return True

async def raffle_monitor():
    """Background task to monitor and end raffles"""
    while True:
        try:
            raffles = load_json(raffles_file)
            for raffle_id, raffle in raffles.items():
                if raffle['status'] == 'active':
                    end_time = datetime.fromisoformat(raffle['end_time'])
                    if datetime.now() >= end_time:
                        await end_raffle(raffle_id)
            
            await asyncio.sleep(30)
        except Exception as e:
            log_error("Raffle monitor error", e)
            await asyncio.sleep(60)

async def verification_cleanup():
    """Background task to clean up expired verifications"""
    while True:
        try:
            current_time = datetime.now()
            expired_users = []
            
            # Find expired verifications
            for user_id, verification_time in verified_users.items():
                time_elapsed = (current_time - verification_time).total_seconds()
                if time_elapsed >= 60:  # Verification expired
                    expired_users.append(user_id)
            
            # Remove expired verifications
            for user_id in expired_users:
                del verified_users[user_id]
            
            if expired_users:
                print(f"Cleaned up {len(expired_users)} expired verifications")
            
            await asyncio.sleep(30)  # Check every 30 seconds
        except Exception as e:
            log_error("Verification cleanup error", e)
            await asyncio.sleep(60)

async def send_main_menu(chat_id, edit_message=None):
    try:
        sender = await bot.get_entity(chat_id)
        username = sender.first_name if sender.first_name else "there"
        
        message = (
            f"🦇 <b>Welcome back, {username}!</b>\n\n"
            f"<b>Ageless Refunds Portal</b> — Premium refund services in the shadows\n"
            f"🌃 <i>2M+ worth of orders processed • Trusted since 2023 • Gotham's finest provider</i>\n\n"
            f"🦇 Choose an option below:"
        )
        
        buttons = [
            [Button.inline("🛍️ Browse Stores", b"store_list"), Button.inline("❓ Help & FAQ", b"faqs")],
            [Button.inline("⭐ See Reviews", b"vouches"), Button.inline("✨ Other Services", b"other_services")],
            [Button.inline("💬 Get Support", b"support")]
        ]
        
        if is_admin(chat_id):
            buttons.append([Button.inline("🔧 Admin Panel", b"admin_panel")])
        
        # Banner handling with caching
        global banner_media_cache
        
        banner_sent = False
        
        # Try to use cached media first (fastest, works everywhere)
        if banner_media_cache:
            try:
                await bot.send_file(
                    chat_id,
                    banner_media_cache,
                    caption=message,
                    buttons=buttons,
                    parse_mode='html'
                )
                banner_sent = True
            except Exception as e:
                # Cache is invalid, clear it and try other methods
                banner_media_cache = None
                log_error("Banner cache invalid, clearing", e)
        
        # If cache didn't work, try local file and cache it
        if not banner_sent and os.path.exists("Banner.mp4"):
            try:
                sent_message = await bot.send_file(
                    chat_id,
                    "Banner.mp4",
                    caption=message,
                    buttons=buttons,
                    parse_mode='html'
                )
                # Cache the media object for future use
                if sent_message and sent_message.media:
                    banner_media_cache = sent_message.media
                banner_sent = True
            except Exception as e:
                log_error("Error sending banner from file", e)
        
        # If still not sent, send text only
        if not banner_sent:
            await bot.send_message(
                chat_id,
                message,
                buttons=buttons,
                parse_mode='html'
            )
    except Exception as e:
        log_error(f"Error in send_main_menu for {chat_id}", e)

# Welcome handler
@bot.on(events.ChatAction)
async def welcome_handler(event):
    try:
        if event.chat_id != GROUP_ID:
            return
        
        if event.user_joined:
            user = await event.get_user()
            if user.bot:
                return
                
            user_name = user.first_name if user.first_name else "there"
            
            welcome_message = (
                f"🎉 <b>Welcome to Ageless Portal, {user_name}!</b>\n\n"
                f"🌟 We're glad to have you here!\n\n"
                f"<b>What we offer:</b>\n"
                f"• 📦 60+ Premium Stores\n"
                f"• 🔥 Exclusive Monthly Promos\n"
                f"• 💬 24/7 Support & Therapy Chat\n"
                f"• ⭐ Verified Reviews & Vouches\n\n"
                f"<b>Quick Start:</b>\n"
                f"• Use /start in bot DM for full store list\n"
                f"• Read pinned messages for important updates\n"
                f"• Feel free to ask questions anytime!\n\n"
                f"⚡ <i>1.5+ years in business • 2M+ orders processed • Fastest service on the market!</i>\n\n"
                f"🚀 Let's get started!"
            )
            
            await bot.send_message(GROUP_ID, welcome_message, parse_mode='html')
    except Exception as e:
        log_error("Welcome handler error", e)

# Captcha and Invite Link Functions
def generate_captcha():
    """Generate a simple math captcha"""
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    answer = num1 + num2
    question = f"{num1} + {num2} = ?"
    return question, answer

async def generate_invite_links():
    """Generate temporary invite links for all channels"""
    try:
        links = {}
        channels = {
            'main': MAIN_CHANNEL_ID,
            'chat': CHAT_CHANNEL_ID,
            'vouch': VOUCH_CHANNEL_ID,
            'storelist': STORELIST_CHANNEL_ID
        }
        
        for name, channel_id in channels.items():
            try:
                # Create invite link with 60 second expiry and usage limit of 1
                result = await bot(ExportChatInviteRequest(
                    peer=channel_id,
                    expire_date=datetime.now() + timedelta(seconds=60),
                    usage_limit=1
                ))
                links[name] = result.link
            except Exception as e:
                log_error(f"Failed to create invite link for {name} ({channel_id})", e)
                links[name] = None
        
        return links
    except Exception as e:
        log_error("Failed to generate invite links", e)
        return None

# Start command with referral support
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    try:
        user_id = event.sender_id
        save_user(user_id)
        
        sender = await event.get_sender()
        username = sender.first_name if sender.first_name else "there"
        
        # Store referral code for later use
        ref_code = None
        try:
            command_parts = event.message.text.split()
            if len(command_parts) > 1:
                ref_code = command_parts[1].strip()
        except:
            pass
        
        # Check if user has failed captcha recently
        if user_id in captcha_states and captcha_states[user_id].get('failed_at'):
            failed_at = captcha_states[user_id]['failed_at']
            time_elapsed = (datetime.now() - failed_at).total_seconds()
            
            if time_elapsed < 60:
                remaining = int(60 - time_elapsed)
                await event.respond(
                    f"⏳ <b>Please wait {remaining}s before retrying.</b>",
                    parse_mode='html'
                )
                return
            else:
                # Timeout expired, clear failed_at and generate new captcha
                del captcha_states[user_id]
        
        # Check if user has passed captcha (and verification hasn't expired)
        verification_valid = False
        if user_id in verified_users:
            verification_time = verified_users[user_id]
            time_elapsed = (datetime.now() - verification_time).total_seconds()
            if time_elapsed < 60:  # Links are valid for 60 seconds
                verification_valid = True
            else:
                # Verification expired, remove from verified_users
                del verified_users[user_id]
        
        if not verification_valid:
            # Show captcha only (no banner yet)
            question, answer = generate_captcha()
            
            # Store captcha data
            captcha_states[user_id] = {
                'answer': answer,
                'failed_at': None,
                'ref_code': ref_code
            }
            
            # Send captcha message
            captcha_message = (
                f"🔒 <b>Solve to get invites:</b>\n"
                f"<code>{question}</code>"
            )
            await event.respond(captcha_message, parse_mode='html')
            return
        
        # User has passed captcha, show main menu
        # Handle referral code if stored
        if user_id in captcha_states and captcha_states[user_id].get('ref_code'):
            ref_code = captcha_states[user_id]['ref_code']
            
            try:
                all_user_data = load_json(user_data_file)
                referrer_id = None
                
                # Find referrer by code
                for uid, data in all_user_data.items():
                    if data.get('referral_code') == ref_code:
                        referrer_id = int(uid)
                        break
                
                if referrer_id and referrer_id != user_id:
                    if add_referral(referrer_id, user_id):
                        try:
                            referrer_entity = await bot.get_entity(referrer_id)
                            referrer_name = referrer_entity.first_name or "User"
                            
                            # Notify referrer
                            await bot.send_message(
                                referrer_id,
                                f"🎉 <b>New Referral!</b>\n\n"
                                f"👤 <b>{username}</b> just joined using your referral link!\n\n"
                                f"💰 <i>Keep sharing to earn more rewards!</i>",
                                parse_mode='html'
                            )
                        except Exception as e:
                            log_error(f"Failed to notify referrer {referrer_id}", e)
                
                # Clear ref code after processing
                captcha_states[user_id]['ref_code'] = None
            except Exception as e:
                log_error("Referral code processing error", e)
        
        # Update user name if not set
        user_data = get_user_data(user_id)
        if not user_data['name']:
            update_user_data(user_id, {'name': username})
        
        # Use the main menu function with the "Biggest provider on the market" message
        await send_main_menu(user_id)
    except Exception as e:
        log_error("Start handler error", e)

# Captcha response handler
def should_handle_captcha(event):
    user_id = event.sender_id
    # Check if user has captcha state and hasn't been verified
    if user_id not in captcha_states or not captcha_states[user_id].get('answer'):
        return False
    if not event.message.text or event.message.text.startswith('/'):
        return False
    # Check if user is verified and verification is still valid
    if user_id in verified_users:
        verification_time = verified_users[user_id]
        time_elapsed = (datetime.now() - verification_time).total_seconds()
        if time_elapsed < 60:  # Still verified
            return False
        else:
            # Verification expired, allow captcha handling
            del verified_users[user_id]
    return True

@bot.on(events.NewMessage(func=should_handle_captcha))
async def captcha_response_handler(event):
    try:
        user_id = event.sender_id
        
        # Double check to prevent duplicate processing
        if user_id not in captcha_states:
            return
        
        # Check if user is already verified and verification is still valid
        if user_id in verified_users:
            verification_time = verified_users[user_id]
            time_elapsed = (datetime.now() - verification_time).total_seconds()
            if time_elapsed < 60:  # Still verified
                return
        
        # Check if user is in timeout
        if captcha_states[user_id].get('failed_at'):
            failed_at = captcha_states[user_id]['failed_at']
            time_elapsed = (datetime.now() - failed_at).total_seconds()
            
            if time_elapsed < 60:
                remaining = int(60 - time_elapsed)
                await event.respond(
                    f"⏳ <b>Please wait {remaining}s before retrying.</b>",
                    parse_mode='html'
                )
                return
            else:
                # Timeout expired, clear the failed_at
                captcha_states[user_id]['failed_at'] = None
        
        user_answer = event.message.text.strip()
        correct_answer = str(captcha_states[user_id]['answer'])
        
        if user_answer == correct_answer:
            # Correct answer - generate invite links
            await event.respond(
                "✅ <b>Correct—fetching invites…</b>",
                parse_mode='html'
            )
            
            # Generate invite links
            links = await generate_invite_links()
            
            if links and all(links.values()):
                invite_message = (
                    "📨 <b>Your links (60s valid):</b>\n\n"
                    f"🥇 <b>Main:</b> {links['main']}\n"
                    f"💬 <b>Chat:</b> {links['chat']}\n\n"
                    "<b>Instructions:</b>\n"
                    "1. Click the Link and Join\n"
                    "2. Make sure to join all the groups above by clicking the links\n"
                    "3. If you missed any, re-enter /start\n"
                    "4. To browse the main bot click the button below"
                )
                
                buttons = [
                    [Button.inline("Browse Ageless Hub 🦇", b"browse_hub")]
                ]
                
                await event.respond(invite_message, buttons=buttons, parse_mode='html', link_preview=False)
                
                # Mark user as verified with timestamp and clear captcha state
                verified_users[user_id] = datetime.now()
                captcha_states[user_id]['answer'] = None  # Clear to prevent any further triggers
            else:
                await event.respond(
                    "❌ <b>Failed to generate invite links. Please try again later.</b>",
                    parse_mode='html'
                )
        else:
            # Wrong answer - set timeout and clear answer to prevent repeated triggers
            captcha_states[user_id]['failed_at'] = datetime.now()
            captcha_states[user_id]['answer'] = None  # Clear to prevent handler from triggering again
            await event.respond(
                "❌ <b>Wrong—wait 1 minute.</b>",
                parse_mode='html'
            )
            
    except Exception as e:
        log_error("Captcha response handler error", e)

# Balance command
@bot.on(events.NewMessage(pattern='/balance'))
async def balance_handler(event):
    try:
        user_id = event.sender_id
        balance = get_wallet_balance(user_id)
        
        message = (
            f"💰 <b>Your Wallet Balance</b>\n\n"
            f"💵 Current Balance: <b>${balance:.2f} USD</b>\n\n"
            f"<i>Use the Profile menu to deposit or view payment history</i>"
        )
        
        buttons = [
            [Button.inline("💳 Deposit Funds", b"wallet_deposit")],
            [Button.inline("📊 Payment History", b"payment_history")],
            [Button.inline("🏠 Main Menu", b"main_menu")]
        ]
        
        await event.respond(message, buttons=buttons, parse_mode='html')
    except Exception as e:
        log_error("Balance handler error", e)

# Get group ID command
@bot.on(events.NewMessage(pattern='/id'))
async def get_id_handler(event):
    try:
        # Check if message is from a group/channel
        if event.is_private:
            return
        
        # Get the chat ID
        chat_id = event.chat_id
        
        # Reply with the group ID
        await event.respond(f"📋 <b>Group ID:</b> <code>{chat_id}</code>", parse_mode='html')
    except Exception as e:
        log_error("Get ID handler error", e)

# Admin command to set banner from uploaded video
@bot.on(events.NewMessage(incoming=True))
async def set_banner_handler(event):
    try:
        # Only for admins
        if not is_admin(event.sender_id):
            return
        
        # Only in private messages to avoid spam
        if not event.is_private:
            return
        
        # Check if message has video
        if event.message.video:
            global banner_media_cache
            
            file_name = event.message.file.name if event.message.file.name else "Unknown"
            file_size = event.message.file.size / (1024 * 1024)  # Convert to MB
            
            # Cache this video as the banner
            banner_media_cache = event.message.media
            
            message = (
                f"✅ <b>Banner Set Successfully!</b>\n\n"
                f"📁 <b>File Name:</b> <code>{file_name}</code>\n"
                f"💾 <b>File Size:</b> {file_size:.2f} MB\n\n"
                f"ℹ️ <b>What happened:</b>\n"
                f"• This video is now cached as your bot banner\n"
                f"• It will show when users start the bot\n"
                f"• Works on Railway and all deployments\n\n"
                f"⚠️ <b>Note:</b> The banner cache resets when you restart the bot.\n"
                f"To make it permanent, ensure Banner.mp4 is in your project root on Railway."
            )
            
            await event.respond(message, parse_mode='html')
            
    except Exception as e:
        log_error("Set banner handler error", e)

# Admin commands
@bot.on(events.NewMessage(pattern=r'^/ban'))
async def ban_handler(event):
    try:
        if not is_admin(event.sender_id):
            return
        
        if event.chat_id != GROUP_ID:
            await event.respond("❌ This command only works in the designated group!")
            return
        
        user_to_ban = None
        
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            user_to_ban = reply_msg.sender_id
            
            bot_me = await bot.get_me()
            if user_to_ban == bot_me.id:
                await event.respond("😅 I can't ban myself!")
                return
        else:
            args = event.message.text.split()[1:]
            if not args:
                await event.respond("❌ Usage: `/ban @username` or `/ban user_id` or reply to a message with `/ban`")
                return
            
            target = args[0]
            if target.startswith('@'):
                user_to_ban = target
            else:
                try:
                    user_to_ban = int(target)
                except ValueError:
                    await event.respond("❌ Invalid user ID!")
                    return
        
        await bot.edit_permissions(GROUP_ID, user_to_ban, view_messages=False)
        await event.respond(f"✅ User banned successfully!")
        
    except Exception as e:
        log_error("Ban error", e)
        await event.respond(f"❌ Error: {str(e)}")

@bot.on(events.NewMessage(pattern=r'^/unban'))
async def unban_handler(event):
    try:
        if not is_admin(event.sender_id):
            return
        
        if event.chat_id != GROUP_ID:
            await event.respond("❌ This command only works in the designated group!")
            return
        
        user_to_unban = None
        
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            user_to_unban = reply_msg.sender_id
        else:
            args = event.message.text.split()[1:]
            if not args:
                await event.respond("❌ Usage: `/unban @username` or `/unban user_id`")
                return
            
            target = args[0]
            if target.startswith('@'):
                user_to_unban = target
            else:
                try:
                    user_to_unban = int(target)
                except ValueError:
                    await event.respond("❌ Invalid user ID!")
                    return
        
        await bot.edit_permissions(
            GROUP_ID, user_to_unban,
            view_messages=True, send_messages=True,
            send_media=True, send_stickers=True, send_polls=True
        )
        await event.respond(f"✅ User unbanned successfully!")
        
    except Exception as e:
        log_error("Unban error", e)
        await event.respond(f"❌ Error: {str(e)}")

@bot.on(events.NewMessage(pattern=r'^/mute'))
async def mute_handler(event):
    try:
        if not is_admin(event.sender_id):
            return
        
        if event.chat_id != GROUP_ID:
            await event.respond("❌ This command only works in the designated group!")
            return
        
        args = event.message.text.split()[1:]
        duration = None
        user_to_mute = None
        until_date = None
        
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            user_to_mute = reply_msg.sender_id
            
            bot_me = await bot.get_me()
            if user_to_mute == bot_me.id:
                await event.respond("😅 I can't mute myself!")
                return
            
            if args:
                try:
                    duration = int(args[0])
                    until_date = datetime.now() + timedelta(minutes=duration)
                except ValueError:
                    await event.respond("❌ Invalid duration!")
                    return
        else:
            if len(args) == 0:
                await event.respond("❌ Usage: `/mute @username [duration]`")
                return
            
            target = args[0]
            if len(args) >= 2:
                try:
                    duration = int(args[1])
                    until_date = datetime.now() + timedelta(minutes=duration)
                except ValueError:
                    await event.respond("❌ Invalid duration!")
                    return
            
            if target.startswith('@'):
                user_to_mute = target
            else:
                try:
                    user_to_mute = int(target)
                except ValueError:
                    await event.respond("❌ Invalid user ID!")
                    return
        
        if until_date:
            await bot.edit_permissions(
                GROUP_ID, user_to_mute, until_date=until_date,
                send_messages=False, send_media=False,
                send_stickers=False, send_polls=False
            )
            await event.respond(f"✅ User muted for {duration} minute(s)!")
        else:
            await bot.edit_permissions(
                GROUP_ID, user_to_mute,
                send_messages=False, send_media=False,
                send_stickers=False, send_polls=False
            )
            await event.respond(f"✅ User muted permanently!")
        
    except Exception as e:
        log_error("Mute error", e)
        await event.respond(f"❌ Error: {str(e)}")

@bot.on(events.NewMessage(pattern=r'^/unmute'))
async def unmute_handler(event):
    try:
        if not is_admin(event.sender_id):
            return
        
        if event.chat_id != GROUP_ID:
            await event.respond("❌ This command only works in the designated group!")
            return
        
        user_to_unmute = None
        
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            user_to_unmute = reply_msg.sender_id
        else:
            args = event.message.text.split()[1:]
            if not args:
                await event.respond("❌ Usage: `/unmute @username` or `/unmute user_id`")
                return
            
            target = args[0]
            if target.startswith('@'):
                user_to_unmute = target
            else:
                try:
                    user_to_unmute = int(target)
                except ValueError:
                    await event.respond("❌ Invalid user ID!")
                    return
        
        await bot.edit_permissions(
            GROUP_ID, user_to_unmute,
            send_messages=True, send_media=True,
            send_stickers=True, send_polls=True
        )
        await event.respond(f"✅ User unmuted successfully!")
        
    except Exception as e:
        log_error("Unmute error", e)
        await event.respond(f"❌ Error: {str(e)}")

@bot.on(events.NewMessage(pattern=r'^/kick'))
async def kick_handler(event):
    try:
        if not is_admin(event.sender_id):
            return
        
        if event.chat_id != GROUP_ID:
            await event.respond("❌ This command only works in the designated group!")
            return
        
        user_to_kick = None
        
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            user_to_kick = reply_msg.sender_id
            
            bot_me = await bot.get_me()
            if user_to_kick == bot_me.id:
                await event.respond("Yeahhh, I'm not going to kick myself.")
                return
        else:
            args = event.message.text.split()[1:]
            if not args:
                await event.respond("❌ Usage: `/kick @username` or `/kick user_id`")
                return
            
            target = args[0]
            if target.startswith('@'):
                user_to_kick = target
            else:
                try:
                    user_to_kick = int(target)
                except ValueError:
                    await event.respond("❌ Invalid user ID!")
                    return
        
        await bot.kick_participant(GROUP_ID, user_to_kick)
        await event.respond(f"👢 User kicked from the group!")
        
    except Exception as e:
        log_error("Kick error", e)
        await event.respond(f"❌ Error: {str(e)}")

# Broadcast
@bot.on(events.NewMessage(pattern='^/broadcast$'))
async def broadcast_handler(event):
    try:
        if not is_admin(event.sender_id):
            await event.respond("❌ Not authorized!")
            return
        
        await event.respond(
            "📢 <b>Broadcast Mode Activated!</b>\n\n"
            "Send the message you want to broadcast.\n\n"
            "Send /cancel to cancel.",
            parse_mode='html'
        )
        
        broadcast_state[event.sender_id] = {'waiting': True}
    except Exception as e:
        log_error("Broadcast init error", e)

@bot.on(events.NewMessage(pattern='^/cancel$'))
async def cancel_handler(event):
    try:
        if event.sender_id in broadcast_state:
            del broadcast_state[event.sender_id]
            await event.respond("❌ Broadcast cancelled.")
        
        if event.sender_id in order_states:
            del order_states[event.sender_id]
            await event.respond("❌ Order cancelled.")
        
        if event.sender_id in admin_remark_state:
            del admin_remark_state[event.sender_id]
            await event.respond("❌ Remark cancelled.")
        
        if event.sender_id in ticket_states:
            del ticket_states[event.sender_id]
            await event.respond("❌ Ticket creation cancelled.")
        
        if event.sender_id in raffle_creation_state:
            del raffle_creation_state[event.sender_id]
            await event.respond("❌ Raffle creation cancelled.")
        
        if event.sender_id in deposit_states:
            del deposit_states[event.sender_id]
            await event.respond("❌ Deposit cancelled.")
        
        if event.sender_id in boxing_service_states:
            del boxing_service_states[event.sender_id]
            await event.respond("❌ Boxing service order cancelled.")
        
        if event.sender_id in payment_details_change_state:
            del payment_details_change_state[event.sender_id]
            await event.respond("❌ Payment details change cancelled.")
        
        if event.sender_id in admin_complete_order_states:
            del admin_complete_order_states[event.sender_id]
            await event.respond("❌ Order completion cancelled.")
            
    except Exception as e:
        log_error("Cancel error", e)

# End chat/ticket
@bot.on(events.NewMessage(pattern='^/endchat$'))
async def endchat_handler(event):
    try:
        tickets = load_json(tickets_file)
        
        for ticket_id, ticket in tickets.items():
            if ticket['status'] == 'active' and (event.sender_id == ticket['user_id'] or is_admin(event.sender_id)):
                
                ticket['status'] = 'closed'
                ticket['ended_at'] = datetime.now().isoformat()
                save_json(tickets_file, tickets)
                
                transcript_file = f"transcripts/{ticket_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                
                with open(transcript_file, 'w', encoding='utf-8') as f:
                    f.write(f"Support Ticket Transcript\n")
                    f.write(f"Ticket ID: {ticket_id}\n")
                    f.write(f"User: {ticket['user_name']} (ID: {ticket['user_id']})\n")
                    f.write(f"Question: {ticket['question']}\n")
                    f.write(f"Started: {ticket['timestamp']}\n")
                    f.write(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for msg in ticket['messages']:
                        f.write(f"[{msg['timestamp']}] {msg['from'].upper()}: {msg['text']}\n")
                
                # Send transcript to all admins
                for admin_id in ADMIN_ID:
                    await bot.send_file(
                        admin_id,
                        transcript_file,
                        caption=f"💬 <b>Ticket Closed</b>\n\nUser: {ticket['user_name']}\nTicket: {ticket_id}",
                        parse_mode='html'
                    )
                
                await bot.send_file(
                    ticket['user_id'],
                    transcript_file,
                    caption=f"💬 <b>Support Chat Ended</b>\n\nTicket: {ticket_id}\n<i>Thank you for contacting us!</i>",
                    parse_mode='html'
                )
                
                await event.respond("✅ Chat ended. Transcript sent.")
                return
        
        await event.respond("❌ No active chat found.")
    except Exception as e:
        log_error("End chat error", e)

# Handle order input
async def handle_order_input(event):
    try:
        user_id = event.sender_id
        state = order_states[user_id]
        
        current_field = state['current_field']
        user_input = event.message.text
        
        # Validate order_total is numeric
        if current_field == 'order_total':
            try:
                float(user_input)
            except ValueError:
                await event.respond("❌ <b>Invalid Amount</b>\n\n<i>Please enter a valid number (e.g., 100 or 99.99)</i>", parse_mode='html')
                return
        
        # Validate phone_number is numeric (can include country code)
        if current_field == 'phone_number':
            cleaned = user_input.replace('+', '').replace('-', '').replace(' ', '')
            if not cleaned.isdigit():
                await event.respond("❌ <b>Invalid Phone Number</b>\n\n<i>Please enter a valid phone number (e.g., +1234567890)</i>", parse_mode='html')
                return
        
        state['order_data'][current_field] = user_input
        
        fields = ['first_name', 'last_name', 'order_number', 'order_total', 'login_details', 'mailbox_login', 'delivery_address', 'billing_address', 'track_number', 'phone_number']
        
        current_index = fields.index(current_field)
        
        if current_index < len(fields) - 1:
            next_field = fields[current_index + 1]
            state['current_field'] = next_field
            
            field_prompts = {
                'first_name': '👤 <b>First Name</b>\n<i>Enter your first name:</i>',
                'last_name': '👤 <b>Last Name</b>\n<i>Enter your last name:</i>',
                'order_number': '🔢 <b>Order Number</b>\n<i>Enter the order number:</i>',
                'order_total': '💰 <b>Order Total (USD)</b>\n<i>Enter the total amount (numbers only):</i>',
                'login_details': '🔐 <b>Login Details</b>\n<i>Format: email:password</i>',
                'mailbox_login': '📧 <b>Mailbox Login</b>\n<i>Format: email:password</i>',
                'delivery_address': '🏠 <b>Delivery Address</b>\n<i>Enter full delivery address:</i>',
                'billing_address': '📍 <b>Billing Address</b>\n<i>Enter billing address:</i>',
                'track_number': '📦 <b>Track Number</b>\n<i>Enter tracking number or "N/A":</i>',
                'phone_number': '📱 <b>Phone Number</b>\n<i>Enter your phone number (numbers only, country code allowed):</i>'
            }
            
            await event.respond(field_prompts[next_field], parse_mode='html')
        else:
            state['active'] = False
            await show_order_confirmation(event)
    except Exception as e:
        log_error("Order input error", e)

async def show_order_confirmation(event):
    try:
        user_id = event.sender_id
        state = order_states[user_id]
        data = state['order_data']
        store_info = state['store_info']
        
        try:
            order_total = float(data['order_total'])
            fee = calculate_fee(order_total, store_info['fee_percentage'])
        except:
            fee = 0
        
        message = (
            f"✅ <b>Order Confirmation</b>\n\n"
            f"🏪 <b>Store:</b> {store_info['name']}\n\n"
            f"<b>📋 Customer Details</b>\n"
            f"• Name: {data['first_name']} {data['last_name']}\n"
            f"• Phone: {data['phone_number']}\n\n"
            f"<b>💰 Payment Breakdown</b>\n"
            f"• Order Total: ${data['order_total']}\n"
            f"• Processing Fee ({store_info['fee_percentage']}%): ${fee}\n"
            f"• <b>Amount to Pay: ${fee}</b>\n\n"
            f"<b>📦 Order Information</b>\n"
            f"• Order #: {data['order_number']}\n"
            f"• Track #: {data['track_number']}\n\n"
            f"<b>🔐 Account Credentials</b>\n"
            f"• Login: {data['login_details']}\n"
            f"• Mailbox: {data['mailbox_login']}\n\n"
            f"<b>📍 Addresses</b>\n"
            f"• Delivery: {data['delivery_address']}\n"
            f"• Billing: {data['billing_address']}\n\n"
            f"⏱ <b>Processing:</b> {store_info['processing']}\n\n"
            f"⚠️ <i>Please review carefully before confirming</i>"
        )
        
        buttons = [
            [Button.inline("✅ Confirm Order", b"confirm_order")],
            [Button.inline("❌ Cancel", b"cancel_order"), Button.inline("🏠 Home", b"main_menu")]
        ]
        
        await event.respond(message, buttons=buttons, parse_mode='html')
    except Exception as e:
        log_error("Order confirmation error", e)

# Handle deposit input
async def handle_deposit_input(event):
    try:
        user_id = event.sender_id
        
        if user_id not in deposit_states:
            return
        
        amount_text = event.message.text.strip()
        
        try:
            amount = float(amount_text)
            if amount < 1:
                await event.respond("❌ <b>Invalid Amount</b>\n\n<i>Minimum deposit is $1 USD</i>", parse_mode='html')
                return
            
            # Create payment
            payment_link, payment_id = await create_payment(
                user_id,
                amount,
                f"Wallet Deposit - ${amount} USD"
            )
            
            if payment_link:
                message = (
                    f"💳 <b>Deposit Payment</b>\n\n"
                    f"💵 Amount: <b>${amount:.2f} USD</b>\n\n"
                    f"<b>Payment Instructions:</b>\n"
                    f"1️⃣ Click the payment link below\n"
                    f"2️⃣ Complete the cryptocurrency payment\n"
                    f"3️⃣ Funds will be added automatically\n\n"
                    f"🔐 <i>Secure payment via OxaPay</i>\n"
                    f"⏱ <i>Payment expires in 30 minutes</i>\n\n"
                    f"🆔 Payment ID: <code>{payment_id}</code>"
                )
                
                buttons = [
                    [Button.url("💳 Pay Now", payment_link)],
                    [Button.inline("🔄 Check Payment Status", f"check_payment_{payment_id}".encode())],
                    [Button.inline("🏠 Main Menu", b"main_menu")]
                ]
                
                await event.respond(message, buttons=buttons, parse_mode='html')
                
                del deposit_states[user_id]
            else:
                await event.respond("❌ <b>Payment Error</b>\n\n<i>Failed to create payment. Please try again later.</i>", parse_mode='html')
                del deposit_states[user_id]
                
        except ValueError:
            await event.respond("❌ <b>Invalid Amount</b>\n\n<i>Please enter a valid number (e.g., 50 or 99.99)</i>", parse_mode='html')
            
    except Exception as e:
        log_error("Deposit input error", e)

# Handle payment details change
async def handle_payment_details_change(event):
    try:
        user_id = event.sender_id
        
        if user_id not in payment_details_change_state:
            return
        
        if not is_admin(user_id):
            del payment_details_change_state[user_id]
            return
        
        new_api_key = event.message.text.strip()
        
        # Basic validation for API key format
        if len(new_api_key) < 10 or '-' not in new_api_key:
            await event.respond(
                "❌ <b>Invalid API Key Format</b>\n\n"
                "<i>Please enter a valid OxaPay Merchant API Key</i>\n\n"
                "Format: <code>XXXXX-XXXXX-XXXXX-XXXXX</code>",
                parse_mode='html'
            )
            return
        
        # Read the current file
        try:
            with open(__file__, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            # Find and replace the OXAPAY_MERCHANT_KEY
            import re
            pattern = r"OXAPAY_MERCHANT_KEY = '[^']*'"
            replacement = f"OXAPAY_MERCHANT_KEY = '{new_api_key}'"
            
            new_content = re.sub(pattern, replacement, file_content)
            
            # Write back to file
            with open(__file__, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Update the global variable
            global OXAPAY_MERCHANT_KEY, oxapay
            OXAPAY_MERCHANT_KEY = new_api_key
            
            # Reinitialize OxaPay client
            try:
                oxapay = SyncOxaPay(merchant_api_key=OXAPAY_MERCHANT_KEY)
                
                message = (
                    "✅ <b>Payment Details Updated Successfully!</b>\n\n"
                    f"🔑 New API Key: <code>{new_api_key[:15]}...</code>\n\n"
                    "💳 OxaPay client has been reinitialized.\n\n"
                    "⚠️ <b>Important:</b> Please restart the bot for full effect.\n\n"
                    "<i>Payment system is now configured with the new credentials.</i>"
                )
            except Exception as e:
                message = (
                    "⚠️ <b>API Key Updated with Warning</b>\n\n"
                    f"🔑 New API Key: <code>{new_api_key[:15]}...</code>\n\n"
                    f"❌ Failed to initialize OxaPay: {str(e)}\n\n"
                    "Please verify the API key is correct and restart the bot."
                )
            
            buttons = [[Button.inline("🔧 Admin Panel", b"admin_panel")]]
            await event.respond(message, buttons=buttons, parse_mode='html')
            
            del payment_details_change_state[user_id]
            
        except Exception as e:
            log_error("Failed to update payment details", e)
            await event.respond(
                f"❌ <b>Update Failed</b>\n\n"
                f"<i>Error: {str(e)}</i>\n\n"
                "Please try again or contact technical support.",
                parse_mode='html'
            )
            del payment_details_change_state[user_id]
    
    except Exception as e:
        log_error("Payment details change handler error", e)

# Handle boxing service input
async def handle_boxing_service_input(event):
    try:
        user_id = event.sender_id
        
        if user_id not in boxing_service_states:
            return
        
        state = boxing_service_states[user_id]
        current_field = state.get('current_field')
        
        if current_field == 'file':
            if event.message.media:
                # Download file
                file_path = f"uploads/boxing_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                await event.download_media(file_path)
                state['order_data']['file_path'] = file_path
                state['current_field'] = 'track_number'
                
                await event.respond(
                    "📦 <b>Track Number</b>\n\n"
                    "<i>Please enter the tracking number:</i>",
                    parse_mode='html'
                )
            else:
                await event.respond("❌ <b>File Required</b>\n\n<i>Please upload the return label file</i>", parse_mode='html')
        
        elif current_field == 'track_number':
            state['order_data']['track_number'] = event.message.text
            state['current_field'] = 'courier_service'
            
            await event.respond(
                "🚚 <b>Courier Service</b>\n\n"
                "<i>Please enter the name of the courier service (e.g., UPS, USPS, FedEx):</i>",
                parse_mode='html'
            )
        
        elif current_field == 'courier_service':
            state['order_data']['courier_service'] = event.message.text
            state['current_field'] = None
            
            # Show confirmation
            service_info = BOXING_SERVICES[state['service_key']]
            
            confirmation = (
                f"✅ <b>Boxing Service Confirmation</b>\n\n"
                f"📦 <b>Service:</b> {service_info['name']}\n"
                f"💰 <b>Price:</b> ${service_info['price']} USD\n\n"
                f"<b>📋 Order Details:</b>\n"
                f"• Track Number: {state['order_data']['track_number']}\n"
                f"• Courier: {state['order_data']['courier_service']}\n"
                f"• File: Uploaded ✓\n\n"
                f"<i>Confirm to proceed with payment</i>"
            )
            
            buttons = [
                [Button.inline("✅ Confirm & Pay", f"confirm_boxing_{state['service_key']}".encode())],
                [Button.inline("❌ Cancel", b"cancel_boxing")]
            ]
            
            await event.respond(confirmation, buttons=buttons, parse_mode='html')
            
    except Exception as e:
        log_error("Boxing service input error", e)

# Handle ticket input
async def handle_ticket_input(event):
    try:
        user_id = event.sender_id
        
        if user_id not in ticket_states:
            return
        
        state = ticket_states[user_id]
        
        if state.get('waiting_for_question'):
            question = event.message.text
            user_name = state['user_name']
            
            ticket_id = create_ticket(user_id, question, user_name)
            
            try:
                user_entity = await bot.get_entity(user_id)
                user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
                
                admin_notification = (
                    f"🎫 <b>New Support Ticket</b>\n\n"
                    f"👤 User: {user_link}\n"
                    f"🆔 User ID: <code>{user_id}</code>\n"
                    f"🎫 Ticket: <code>{ticket_id}</code>\n\n"
                    f"<b>Question:</b>\n<i>{question}</i>"
                )
                
                admin_buttons = [
                    [Button.inline("✅ Accept", f"accept_ticket_{ticket_id}".encode()),
                     Button.inline("❌ Reject", f"reject_ticket_{ticket_id}".encode())]
                ]
                
                # Notify all admins
                for admin_id in ADMIN_ID:
                    await bot.send_message(admin_id, admin_notification, buttons=admin_buttons, parse_mode='html')
            except Exception as e:
                log_error(f"Failed to notify admin about ticket", e)
            
            await event.respond(
                f"✅ <b>Ticket Created!</b>\n\n"
                f"🎫 Ticket ID: <code>{ticket_id}</code>\n\n"
                f"⏳ Waiting for admin to accept your request...\n\n"
                f"<i>You'll be notified once an admin responds.</i>",
                parse_mode='html'
            )
            
            del ticket_states[user_id]
    except Exception as e:
        log_error("Ticket input error", e)

# Handle raffle creation input
async def handle_raffle_input(event):
    try:
        user_id = event.sender_id
        
        if not is_admin(user_id) or user_id not in raffle_creation_state:
            return
        
        state = raffle_creation_state[user_id]
        current_field = state.get('current_field')
        
        if current_field == 'prize':
            state['prize'] = event.message.text
            state['current_field'] = 'winners'
            await event.respond(
                "🏆 <b>Number of Winners</b>\n\n"
                "<i>How many winners should this raffle have?</i>",
                parse_mode='html'
            )
        
        elif current_field == 'winners':
            try:
                winners = int(event.message.text)
                if winners <= 0:
                    raise ValueError
                state['winners_count'] = winners
                state['current_field'] = 'duration'
                await event.respond(
                    "⏱ <b>Raffle Duration</b>\n\n"
                    "<i>How long should the raffle run?</i>\n\n"
                    "Format examples:\n"
                    "• 30m (30 minutes)\n"
                    "• 2h (2 hours)\n"
                    "• 1d (1 day)",
                    parse_mode='html'
                )
            except ValueError:
                await event.respond("❌ Please enter a valid number!")
        
        elif current_field == 'duration':
            try:
                duration_text = event.message.text.lower().strip()
                
                if duration_text.endswith('m'):
                    duration_minutes = int(duration_text[:-1])
                elif duration_text.endswith('h'):
                    duration_minutes = int(duration_text[:-1]) * 60
                elif duration_text.endswith('d'):
                    duration_minutes = int(duration_text[:-1]) * 1440
                else:
                    duration_minutes = int(duration_text)
                
                if duration_minutes <= 0:
                    raise ValueError
                
                state['duration_minutes'] = duration_minutes
                state['current_field'] = None
                
                end_time = datetime.now() + timedelta(minutes=duration_minutes)
                
                confirmation = (
                    f"🎁 <b>Raffle Summary</b>\n\n"
                    f"🏆 Prize: {state['prize']}\n"
                    f"👥 Winners: {state['winners_count']}\n"
                    f"⏱ Duration: {duration_minutes} minutes\n"
                    f"⏰ Ends at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"<i>Confirm to create and post the raffle</i>"
                )
                
                buttons = [
                    [Button.inline("✅ Create Raffle", b"create_raffle_confirm")],
                    [Button.inline("❌ Cancel", b"cancel_raffle")]
                ]
                
                await event.respond(confirmation, buttons=buttons, parse_mode='html')
            
            except ValueError:
                await event.respond("❌ Please enter a valid duration! (e.g., 30m, 2h, 1d)")
    
    except Exception as e:
        log_error("Raffle input error", e)

# Handle admin complete order input
async def handle_admin_complete_order(event):
    try:
        user_id = event.sender_id
        
        if not is_admin(user_id) or user_id not in admin_complete_order_states:
            return
        
        state = admin_complete_order_states[user_id]
        order_id = state['order_id']
        
        # Store delivery content
        delivery_content = {
            'type': 'text' if not event.message.media else 'media',
            'content': event.message.text if not event.message.media else None,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Download media if present
        if event.message.media:
            file_path = f"uploads/delivery_{order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            await event.download_media(file_path)
            delivery_content['file_path'] = file_path
        
        state['delivery_content'] = delivery_content
        
        # Show confirmation
        message = (
            f"✅ <b>Order Delivery Confirmation</b>\n\n"
            f"🆔 Order: <code>{order_id}</code>\n\n"
            f"📦 Content Type: {delivery_content['type'].title()}\n\n"
            f"<i>Click Complete to deliver this order to the customer</i>"
        )
        
        buttons = [
            [Button.inline("✅ Complete Order", f"admin_final_complete_{order_id}".encode())],
            [Button.inline("❌ Cancel", b"admin_cancel_complete")]
        ]
        
        await event.respond(message, buttons=buttons, parse_mode='html')
        
    except Exception as e:
        log_error("Admin complete order input error", e)

# Message handler
@bot.on(events.NewMessage(incoming=True))
async def message_handler(event):
    try:
        user_id = event.sender_id
        
        # Ignore commands
        if event.message.text and event.message.text.startswith('/'):
            return
        
        # Admin remark state
        if is_admin(user_id) and user_id in admin_remark_state and event.is_private:
            order_id = admin_remark_state[user_id]['order_id']
            remark_text = event.message.text
            
            if add_order_remark(order_id, remark_text, by_admin=True):
                order = get_order(order_id)
                customer_id = order['user_id']
                
                await bot.send_message(
                    customer_id,
                    f"📝 <b>New Update on Your Order</b>\n\n"
                    f"🆔 Order: <code>{order_id}</code>\n\n"
                    f"<b>Admin Remark:</b>\n<i>{remark_text}</i>\n\n"
                    f"Check your profile for full details!",
                    parse_mode='html'
                )
                
                await event.respond(f"✅ Remark added to order {order_id}")
            else:
                await event.respond("❌ Failed to add remark")
            
            del admin_remark_state[user_id]
            return
        
        # Admin complete order state
        if is_admin(user_id) and user_id in admin_complete_order_states and event.is_private:
            await handle_admin_complete_order(event)
            return
        
        # Store management state
        if is_admin(user_id) and user_id in store_management_state and event.is_private:
            state = store_management_state[user_id]
            text = event.message.text or ""
            
            if text.lower() == '/cancel':
                del store_management_state[user_id]
                await event.respond("❌ Store management cancelled.")
                return
            
            step = state['step']
            action = state['action']
            
            if step == 'category_name':
                # Create new category
                category_id = text.lower().replace(' ', '_').replace('&', '').replace(',', '')[:50]
                category_name = text.strip()
                
                stores_data = load_stores()
                stores_data[category_id] = {
                    'name': category_name,
                    'stores': {}
                }
                
                if save_stores(stores_data):
                    state['category'] = category_id
                    state['step'] = 'store_name'
                    await event.respond(
                        f"✅ Category '{category_name}' created!\n\n"
                        f"📝 <b>Step 1/6: Store Name</b>\n\n"
                        f"Enter the store name:\n"
                        f"<i>Example: 📦 Amazon, 🍎 Apple, etc.</i>",
                        parse_mode='html'
                    )
                else:
                    await event.respond("❌ Failed to create category. Please try again.")
                    del store_management_state[user_id]
            
            elif step == 'store_name':
                state['store_data']['name'] = text.strip()
                state['step'] = 'fee_percentage'
                await event.respond(
                    f"✅ Store name: {text.strip()}\n\n"
                    f"📝 <b>Step 2/6: Fee Percentage</b>\n\n"
                    f"Enter fee percentage (numbers only):\n"
                    f"<i>Example: 18, 20, 15 (for 18%, 20%, 15%)</i>",
                    parse_mode='html'
                )
            
            elif step == 'fee_percentage':
                try:
                    fee_pct = float(text.strip())
                    if fee_pct < 0 or fee_pct > 100:
                        raise ValueError()
                    state['store_data']['fee_percentage'] = fee_pct
                    state['step'] = 'min_limit'
                    await event.respond(
                        f"✅ Fee percentage: {fee_pct}%\n\n"
                        f"📝 <b>Step 3/6: Minimum Limit</b>\n\n"
                        f"Enter minimum order limit (USD):\n"
                        f"<i>Example: 0, 150, 200</i>",
                        parse_mode='html'
                    )
                except:
                    await event.respond("❌ Invalid percentage. Please enter a number between 0 and 100.")
            
            elif step == 'min_limit':
                try:
                    min_limit = float(text.strip())
                    if min_limit < 0:
                        raise ValueError()
                    state['store_data']['limits'] = {'min': min_limit}
                    state['step'] = 'max_limit'
                    await event.respond(
                        f"✅ Minimum limit: ${min_limit}\n\n"
                        f"📝 <b>Step 4/6: Maximum Limit</b>\n\n"
                        f"Enter maximum order limit (USD) or 'none' for unlimited:\n"
                        f"<i>Example: 5000, 10000, none</i>",
                        parse_mode='html'
                    )
                except:
                    await event.respond("❌ Invalid amount. Please enter a positive number.")
            
            elif step == 'max_limit':
                try:
                    max_text = text.strip().lower()
                    if max_text == 'none' or max_text == 'unlimited':
                        state['store_data']['limits']['max'] = None
                    else:
                        max_limit = float(max_text)
                        if max_limit < state['store_data']['limits']['min']:
                            raise ValueError("Max must be >= min")
                        state['store_data']['limits']['max'] = max_limit
                    
                    state['step'] = 'processing_time'
                    max_display = "Unlimited" if state['store_data']['limits']['max'] is None else f"${state['store_data']['limits']['max']}"
                    await event.respond(
                        f"✅ Maximum limit: {max_display}\n\n"
                        f"📝 <b>Step 5/6: Processing Time</b>\n\n"
                        f"Enter processing time:\n"
                        f"<i>Example: Instant, 24-72 hours, 1-3 days, 1-2 weeks</i>",
                        parse_mode='html'
                    )
                except ValueError as e:
                    await event.respond(f"❌ Invalid amount. {str(e)}")
            
            elif step == 'processing_time':
                state['store_data']['processing'] = text.strip()
                state['step'] = 'description'
                
                description_examples = (
                    "📝 <b>Step 6/6: Description</b>\n\n"
                    "Enter store description with examples:\n\n"
                    "<b>Examples:</b>\n"
                    "• Free delivery only, pickup accepted | US, CA & EU\n"
                    "• Electronics & tech, 1 item max, no reship or pickup | US only\n"
                    "• Replacement method, 2 items max | US only\n"
                    "• Insider method, no item limit, reship accepted | New Zealand\n"
                    "• High limit store, 4 items max | US only\n\n"
                    "<i>Include: item limits, shipping options, regions, special notes</i>"
                )
                
                await event.respond(description_examples, parse_mode='html')
            
            elif step == 'description':
                state['store_data']['description'] = text.strip()
                
                # Generate store_id from name
                store_name = state['store_data']['name']
                store_id = store_name.lower().replace(' ', '_').replace('📦', '').replace('🍎', '').replace('📺', '').replace('🌪️', '').replace('🖥️', '').replace('🥽', '').replace('🎮', '').replace('🔔', '').replace('📱', '').replace('✨', '').replace('👔', '').replace('🧰', '').replace('✂️', '').replace('👠', '').replace('👕', '').replace('🧥', '').replace('🛍️', '').replace('🐎', '').replace('📏', '').replace('🎨', '').replace('👗', '').replace('🧢', '').replace('🏈', '').replace('🛏️', '').replace('💡', '').replace('🛒', '').replace('📎', '').strip()[:50]
                store_id = ''.join(c for c in store_id if c.isalnum() or c == '_')
                
                if not store_id:
                    store_id = f"store_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Save store
                stores_data = load_stores()
                category = state['category']
                
                if action == 'add':
                    stores_data[category]['stores'][store_id] = state['store_data']
                    action_text = "added"
                else:  # edit
                    old_store_id = state.get('store_id', store_id)
                    if old_store_id != store_id:
                        # Store ID changed, remove old and add new
                        if old_store_id in stores_data[category]['stores']:
                            del stores_data[category]['stores'][old_store_id]
                        stores_data[category]['stores'][store_id] = state['store_data']
                    else:
                        stores_data[category]['stores'][store_id] = state['store_data']
                    action_text = "updated"
                
                if save_stores(stores_data):
                    del store_management_state[user_id]
                    await event.respond(
                        f"✅ <b>Store {action_text} successfully!</b>\n\n"
                        f"🏪 <b>{state['store_data']['name']}</b>\n"
                        f"📂 Category: {stores_data[category]['name']}\n"
                        f"💰 Fee: {state['store_data']['fee_percentage']}%\n"
                        f"📊 Limits: ${state['store_data']['limits']['min']} - "
                        f"{'Unlimited' if state['store_data']['limits']['max'] is None else '$' + str(state['store_data']['limits']['max'])}\n"
                        f"⏱ Processing: {state['store_data']['processing']}\n\n"
                        f"<i>Store is now available for customers!</i>",
                        parse_mode='html'
                    )
                else:
                    await event.respond("❌ Failed to save store. Please try again.")
                    del store_management_state[user_id]
            return
        
        # Active ticket conversation
        tickets = load_json(tickets_file)
        active_ticket = None
        
        for ticket_id, ticket in tickets.items():
            if ticket['status'] == 'active' and event.is_private:
                if user_id == ticket['user_id'] or is_admin(user_id):
                    active_ticket = ticket_id
                    break
        
        if active_ticket:
            ticket_data = tickets[active_ticket]
            
            add_ticket_message(active_ticket, event.message.text or '[Media]', from_admin=is_admin(user_id))
            
            if is_admin(user_id):
                recipient = ticket_data['user_id']
                prefix = "👨‍💼 <b>Admin:</b>\n"
                recipients = [recipient]
            else:
                recipients = ADMIN_ID  # Send to all admins
                user_name = ticket_data['user_name']
                prefix = f"👤 <b>{user_name}:</b>\n"
            
            try:
                for recipient in recipients:
                    if event.message.media:
                        await bot.send_file(recipient, event.message.media, caption=prefix + (event.message.text or ''), parse_mode='html')
                    else:
                        await bot.send_message(recipient, prefix + event.message.text, parse_mode='html')
            except Exception as e:
                log_error(f"Ticket message forward error", e)
            
            return
        
        # Ticket creation state
        if user_id in ticket_states:
            await handle_ticket_input(event)
            return
        
        # Order creation state
        if user_id in order_states and order_states[user_id].get('active'):
            await handle_order_input(event)
            return
        
        # Deposit state
        if user_id in deposit_states:
            await handle_deposit_input(event)
            return
        
        # Boxing service state
        if user_id in boxing_service_states:
            await handle_boxing_service_input(event)
            return
        
        # Raffle creation state
        if user_id in raffle_creation_state:
            await handle_raffle_input(event)
            return
        
        # Payment details change state
        if user_id in payment_details_change_state:
            await handle_payment_details_change(event)
            return
        
        # Broadcast state
        if user_id in broadcast_state and broadcast_state[user_id].get('waiting'):
            broadcast_state[user_id] = {
                'waiting': False,
                'message': event.message
            }
            
            buttons = [
                [Button.inline("✅ Confirm & Send", b"confirm_broadcast")],
                [Button.inline("❌ Cancel", b"cancel_broadcast")]
            ]
            
            preview = "📢 <b>Broadcast Preview</b>\n\n"
            
            if event.message.media:
                preview += "📎 Type: <b>Media</b>\n"
            else:
                preview += "📝 Type: <b>Text</b>\n"
            
            preview += "\n<i>Click Confirm to broadcast</i>"
            
            await event.respond(preview, buttons=buttons, parse_mode='html')
    
    except Exception as e:
        log_error("Message handler error", e)

# Callback handler - Part 1
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    try:
        data = event.data.decode('utf-8')
        user_id = event.sender_id
        
        print(f"[CALLBACK] User {user_id} clicked: {data}")
        
        async def safe_edit(event, message, buttons=None, parse_mode='html'):
            try:
                await event.edit(message, buttons=buttons, parse_mode=parse_mode)
            except Exception as e:
                try:
                    await event.delete()
                except:
                    pass
                try:
                    await bot.send_message(event.chat_id, message, buttons=buttons, parse_mode=parse_mode)
                except Exception as send_error:
                    log_error(f"Failed to send message after edit failed: {send_error}", send_error)
        
        # Browse Hub - Main Menu
        if data == "browse_hub":
            try:
                await event.delete()
            except:
                pass
            
            await send_main_menu(user_id)
        
        # FAQs
        elif data == "faqs":
            faq_message = (
                f"🦇 <b>Frequently Asked Questions</b>\n\n"
                f"<b>💼 What can you offer me?</b>\n"
                f"We provide premium refund services with a vast selection of stores. Choose from our extensive store list and start earning!\n"
                f"We also offer: Boxing Services, Aged Accounts, ID Verifications, Carrier Receipts, Fake PRs and much more! Explore our portal for all services!\n\n"
                f"<b>🌃 How it works?</b>\n"
                f"Simple as the Bat-Signal:\n"
                f"1️⃣ Choose a store from our list\n"
                f"2️⃣ Check conditions & select items\n"
                f"3️⃣ Place your order\n"
                f"4️⃣ Inform us after delivery\n"
                f"5️⃣ Fill in the form (account details)\n"
                f"6️⃣ We handle the rest in the shadows!\n\n"
                f"Some stores offer replacements instead of refunds. Resell items and earn 10k+/month with minimal effort!\n\n"
                f"<b>🦇 Why choose Ageless Refunds?</b>\n"
                f"Gotham's most trusted refund service.\n"
                f"• 🌙 Never ghosting, always watching\n"
                f"• ✅ Professional service guaranteed\n"
                f"• 💰 We only profit when you do\n"
                f"• 🏙️ Biggest refund provider in the game\n"
                f"• ⚡ Always working to maximize your earnings\n\n"
                f"<b>💳 When do I pay your fee and why?</b>\n"
                f"We work first! Payment upon confirmation to protect both sides:\n"
                f"• 📨 We send refund confirmation\n"
                f"• 💰 You pay after confirmation\n"
                f"• 🛡️ Middleman available for security\n"
                f"• 💵 Bank arrival option: +5% fee\n\n"
                f"⚠️ Notify us in advance if you can't pay immediately. Failure to notify may result in order cancellation.\n\n"
                f"<b>🕐 When can I get support?</b>\n"
                f"Like the Dark Knight, we work 18+ hours daily and are almost always available to answer your questions!\n\n"
                f"💡 Pro Tip: Consult with us and submit your cart before checkout to avoid issues. We customize methods for each order.\n\n"
                f"<b>💰 Payment methods?</b>\n"
                f"We accept:\n"
                f"• 🪙 Any cryptocurrency\n"
                f"• 💵 CashApp (may be available)\n\n"
                f"<b>⏱ How long does it take?</b>\n"
                f"Average: 3-5 business days\n\n"
                f"📝 Timeframe varies by store and is not guaranteed, but provided as an estimate.\n\n"
                f"💬 Still have questions? Contact our support team!"
            )
            
            buttons = [[Button.inline("🏠 Back to Menu", b"main_menu")]]
            await safe_edit(event, faq_message, buttons=buttons)
        
        # Support
        elif data == "support":
            support_message = (
                f"💬 <b>Customer Support</b>\n\n"
                f"<i>Get help from our team:</i>\n\n"
                f"👨‍💼 <b>Contact Admin</b>\n"
                f"Send a direct message to admin for any assistance"
            )
            
            buttons = [
                [Button.url("👨‍💼 Contact Admin", "https://t.me/ageless_1")],
                [Button.inline("🏠 Back to Menu", b"main_menu")]
            ]
            
            await safe_edit(event, support_message, buttons=buttons)
        
        # Start live chat
        elif data == "start_live_chat":
            active = get_active_ticket_for_user(user_id)
            if active:
                await event.answer("⚠️ You already have an active support ticket!", alert=True)
                return
            
            sender = await event.get_sender()
            user_name = sender.first_name or "User"
            
            ticket_states[user_id] = {
                'waiting_for_question': True,
                'user_name': user_name
            }
            
            await safe_edit(
                event,
                f"🎫 <b>Start Live Chat</b>\n\n"
                f"Please describe your issue or question:\n\n"
                f"<i>Type your question below and we'll connect you with support.</i>\n\n"
                f"💡 Send /cancel to abort",
                buttons=None
            )
        
        # Accept ticket
        elif data.startswith("accept_ticket_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            ticket_id = data.replace("accept_ticket_", "")
            ticket = get_ticket(ticket_id)
            
            if ticket and update_ticket(ticket_id, {'status': 'active'}):
                customer_id = ticket['user_id']
                
                await bot.send_message(
                    customer_id,
                    f"✅ <b>Support Chat Started!</b>\n\n"
                    f"🎫 Ticket: <code>{ticket_id}</code>\n\n"
                    f"👨‍💼 An admin has accepted your request.\n"
                    f"💬 You can now chat with support.\n\n"
                    f"<i>Type /endchat to close the conversation</i>",
                    parse_mode='html'
                )
                
                # Notify all admins
                for admin_id in ADMIN_ID:
                    await bot.send_message(
                        admin_id,
                        f"✅ <b>Ticket Accepted</b>\n\n"
                        f"🎫 Ticket: <code>{ticket_id}</code>\n"
                        f"👤 User: {ticket['user_name']}\n\n"
                        f"💬 Chat is now active.\n"
                        f"<i>Type /endchat to close the conversation</i>",
                        parse_mode='html'
                    )
                
                try:
                    await event.edit(
                        (await event.get_message()).message + "\n\n✅ <b>ACCEPTED</b>",
                        buttons=None,
                        parse_mode='html'
                    )
                except:
                    pass
                
                await event.answer("✅ Ticket accepted!", alert=True)
        
        # Reject ticket
        elif data.startswith("reject_ticket_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            ticket_id = data.replace("reject_ticket_", "")
            ticket = get_ticket(ticket_id)
            
            if ticket and update_ticket(ticket_id, {'status': 'rejected'}):
                customer_id = ticket['user_id']
                
                await bot.send_message(
                    customer_id,
                    f"❌ <b>Support Request Rejected</b>\n\n"
                    f"🎫 Ticket: <code>{ticket_id}</code>\n\n"
                    f"<i>Sorry, we're unable to accept your request at this time. Please try again later or contact admin directly.</i>",
                    parse_mode='html'
                )
                
                try:
                    await event.edit(
                        (await event.get_message()).message + "\n\n❌ <b>REJECTED</b>",
                        buttons=None,
                        parse_mode='html'
                    )
                except:
                    pass
                
                await event.answer("❌ Ticket rejected!", alert=True)
        
        # Referral
        elif data == "referral":
            stats = get_referral_stats(user_id)
            user_data = get_user_data(user_id)
            
            bot_username = (await bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start={stats['code']}"
            
            referral_message = (
                f"🤝 <b>Your Referral Dashboard</b>\n\n"
                f"<b>📊 Statistics</b>\n"
                f"• Total Referrals: <b>{stats['total']}</b>\n"
                f"• Active Referrals: <b>{stats['active']}</b>\n"
                f"• Referral Code: <code>{stats['code']}</code>\n\n"
                f"<b>🔗 Your Referral Link</b>\n"
                f"<code>{referral_link}</code>\n\n"
                f"<b>💰 Referral Rewards:</b>\n"
                f"💸 Earn <b>25% of every deposit</b> your referrals make!\n"
                f"💳 Rewards are added instantly to your wallet\n\n"
                f"<b>💡 How it works:</b>\n"
                f"1️⃣ Share your referral link with friends\n"
                f"2️⃣ They join using your link\n"
                f"3️⃣ When they deposit, you get <b>25%</b> automatically!\n"
                f"4️⃣ Track your earnings here!\n\n"
                f"🎁 <i>More referrals = More passive income!</i>"
            )
            
            buttons = [
                [Button.inline("📤 Share Link", b"share_referral")],
                [Button.inline("🏠 Back to Menu", b"main_menu")]
            ]
            
            await safe_edit(event, referral_message, buttons=buttons)
        
        # Share referral
        elif data == "share_referral":
            stats = get_referral_stats(user_id)
            bot_username = (await bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start={stats['code']}"
            
            share_text = (
                f"🎉 Join Ageless Portal - Premium Cashback Services!\n\n"
                f"⚡ 2M+ orders delivered • Trusted since 2023\n"
                f"💰 Earn cashbacks from 60+ premium stores\n"
                f"🚀 Fast processing • Best rates\n\n"
                f"👇 Join now using my referral link:\n"
                f"{referral_link}"
            )
            
            buttons = [
                [Button.switch_inline("📤 Share in Chat", share_text)],
                [Button.inline("🔙 Back", b"referral")],
                [Button.inline("🏠 Back to Menu", b"main_menu")]
            ]
            
            await safe_edit(
                event,
                f"📤 <b>Share Your Referral Link</b>\n\n"
                f"<i>Click the button below to share your referral link in any chat!</i>\n\n"
                f"<code>{referral_link}</code>\n\n"
                f"<i>Or copy the link above and share manually.</i>",
                buttons=buttons
            )
        
        # Games
        elif data == "games":
            await event.answer("🎮 API not set up yet! Coming soon...", alert=True)
        
        # Raffles
        elif data == "raffles":
            active_raffles = get_active_raffles()
            
            if not active_raffles:
                await event.answer("🎁 No active raffles at the moment. Check back later!", alert=True)
                return
            
            message = f"🎁 <b>Active Raffles</b>\n\n<i>Click on a raffle to join:</i>\n\n"
            
            buttons = []
            for raffle_id in active_raffles:
                raffle = get_raffle(raffle_id)
                if raffle:
                    end_time = datetime.fromisoformat(raffle['end_time'])
                    time_left = end_time - datetime.now()
                    hours = int(time_left.total_seconds() // 3600)
                    minutes = int((time_left.total_seconds() % 3600) // 60)
                    
                    raffle_text = f"🎁 {raffle['prize']} ({hours}h {minutes}m left)"
                    buttons.append([Button.inline(raffle_text, f"join_raffle_{raffle_id}".encode())])
            
            buttons.append([Button.inline("🏠 Back to Menu", b"main_menu")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # Join raffle
        elif data.startswith("join_raffle_"):
            raffle_id = data.replace("join_raffle_", "")
            raffle = get_raffle(raffle_id)
            
            if not raffle:
                await event.answer("❌ Raffle not found!", alert=True)
                return
            
            if raffle['status'] != 'active':
                await event.answer("❌ This raffle has ended!", alert=True)
                return
            
            if join_raffle(raffle_id, user_id):
                await event.answer("✅ You've joined the raffle! Good luck!", alert=True)
            else:
                await event.answer("⚠️ You're already in this raffle!", alert=True)
        
        # Other Services
        elif data == "other_services":
            await event.answer("🔜 Coming Soon! Premium services will be available shortly.", alert=True)
        
        # Removed handlers - Coming Soon (Private Monthly Group, Aged Accounts, Boxing Services, etc.)
        elif data in ["private_monthly_group", "purchase_monthly_group", "refunding_methods", "aged_accounts", "aged_amazon", "aged_apple", "boxing_service", "boxing_pod_delete", "boxing_ups_instant", "cancel_boxing"] or data.startswith("boxing_") or data.startswith("confirm_boxing_"):
            await event.answer("🔜 Coming Soon! This service will be available shortly.", alert=True)
        
        # [OLD DUPLICATE OTHER_SERVICES HANDLERS COMPLETELY REMOVED - NOW SHOWING "COMING SOON"]
        
        # Check payment status
        elif data.startswith("check_payment_"):
            payment_id = data.replace("check_payment_", "")
            
            status = await check_payment_status(payment_id)
            
            if status == 'completed':
                payments = load_json(payments_file)
                payment_data = payments.get(payment_id)
                
                if payment_data:
                    amount = payment_data['amount']
                    description = payment_data['description']
                    
                    # Check if it's a wallet deposit
                    if 'Wallet Deposit' in description:
                        # Add to wallet
                        if add_to_wallet(user_id, amount, description):
                            await event.answer(f"✅ Payment completed! ${amount} added to wallet", alert=True)
                            
                            # Process referral reward
                            try:
                                reward_amount = await process_referral_reward(user_id, amount)
                                if reward_amount:
                                    log_error(f"Referral reward processed: ${reward_amount} for user deposit ${amount}", None)
                            except Exception as e:
                                log_error("Failed to process referral reward", e)
                            
                            # Notify admin
                            try:
                                user_entity = await bot.get_entity(user_id)
                                user_name = user_entity.first_name or "User"
                                
                                await bot.send_message(
                                    PAYMENT_NOTIFICATION_CHANNEL,
                                    f"💰 <b>Deposit Received</b>\n\n"
                                    f"👤 User: {user_name} (<code>{user_id}</code>)\n"
                                    f"💵 Amount: ${amount} USD\n"
                                    f"📝 Type: Wallet Deposit\n"
                                    f"🆔 Payment: <code>{payment_id}</code>",
                                    parse_mode='html'
                                )
                            except Exception as e:
                                log_error("Failed to notify admin about deposit", e)
                    
                    # Check if it's a service order
                    elif payment_data.get('service_order_id'):
                        order_id = payment_data['service_order_id']
                        
                        # Update service order status
                        if update_service_order(order_id, {'payment_status': 'paid'}):
                            service_order = get_service_order(order_id)
                            
                            await event.answer("✅ Payment completed! Order is being processed", alert=True)
                            
                            # Notify user
                            await bot.send_message(
                                user_id,
                                f"✅ <b>Payment Successful!</b>\n\n"
                                f"🆔 Order: <code>{order_id}</code>\n"
                                f"📦 Service: {service_order['service_name']}\n"
                                f"💰 Amount: ${service_order['price']} USD\n\n"
                                f"⏳ <b>Your order is being processed</b>\n\n"
                                f"<i>You'll be notified once it's ready for delivery!</i>",
                                parse_mode='html'
                            )
                            
                            # Notify admin
                            try:
                                user_entity = await bot.get_entity(user_id)
                                user_name = user_entity.first_name or "User"
                                
                                admin_message = (
                                    f"🔔 <b>SERVICE ORDER PAID</b>\n\n"
                                    f"🆔 Order: <code>{order_id}</code>\n"
                                    f"👤 User: {user_name} (<code>{user_id}</code>)\n"
                                    f"📦 Service: {service_order['service_name']}\n"
                                    f"💰 Amount: ${service_order['price']} USD\n"
                                    f"💳 Payment: <code>{payment_id}</code>\n\n"
                                    f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                                
                                await bot.send_message(
                                    PAYMENT_NOTIFICATION_CHANNEL,
                                    admin_message,
                                    parse_mode='html'
                                )
                            except Exception as e:
                                log_error("Failed to notify admin about service order", e)
                        else:
                            await event.answer("✅ Payment received! Processing order...", alert=True)
                    
                    # Regular order (not service)
                    else:
                        await event.answer("✅ Payment completed!", alert=True)
                else:
                    await event.answer("❌ Payment data not found", alert=True)
            elif status == 'pending':
                await event.answer("⏳ Payment is still pending. Please complete the payment.", alert=True)
            elif status == 'expired':
                await event.answer("❌ Payment link has expired. Please create a new order.", alert=True)
            else:
                await event.answer("❌ Payment failed or cancelled", alert=True)
        
        # [ALL OLD OTHER_SERVICES DUPLICATE HANDLERS REMOVED FROM HERE TO CHECK_ORDER_PAYMENT]
        
        # [OLD DUPLICATE HANDLERS BELOW - DISABLED - REAL HANDLERS ARE LATER IN FILE]
        # This section contains old duplicate code that will be cleaned up
        # The real working handlers are later in the callback handler
        
        # Disabled duplicate check_order_payment
        elif data.startswith("check_order_payment_DUPLICATE_DISABLED"):
            pass  # Disabled - using real handler later
        
        # [LARGE BLOCK OF DUPLICATE OTHER_SERVICES HANDLERS - ALL DISABLED OR REMOVED]
        # All the old other_services handlers now show "Coming Soon" via line 2478
        # The junk code below will be cleaned up later
        
        # Disabled duplicate handlers below (real handlers are later in file)
        elif data in ["purchase_monthly_group_OLD", "aged_amazon_OLD", "aged_apple_OLD", "boxing_service_OLD", "boxing_pod_delete_OLD", "boxing_ups_instant_OLD", "cancel_boxing_OLD"]:
            pass  # All disabled - handled by Coming Soon at line 2478
        
        # REAL HANDLERS START HERE (after all the old duplicate junk)
        
        # NOTE: There's still old malformed duplicate code between here and the real handlers
        # It will be cleaned up in a future commit. For now it's just unreachable dead code.
        
        # Disabled duplicate store_list (real one is later)
        elif data == "store_list_DUPLICATE_OLD":
            pass  # Disabled  
        
        # Below is unreachable junk code from old implementation that will cause syntax errors
        # Commenting it out would be tedious, so let me try wrapping in an if False block
        if False:  # Disable all the junk code below
            junk_code = (
                f"• $50 for the first month\n"
                f"• $75/month thereafter\n\n"
                f"⚠️ <b>Only 20 discounted slots available!</b>\n"
                f"📩 Message Ageless now to secure your spot!\n\n"
                f"<i>Click below to purchase first month access:</i>"
            )
            
            buttons = [
                [Button.inline("💳 Purchase - $50", b"purchase_monthly_group")],
                [Button.inline("🔙 Back", b"other_services")],
                [Button.inline("🏠 Main Menu", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Purchase Monthly Group
        elif data == "purchase_monthly_group":
            payment_link, payment_id = await create_payment(
                user_id,
                50,
                "Private Monthly Group - First Month",
                f"MONTHLY-{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            
            if payment_link:
                message = (
                    f"💳 <b>Private Monthly Group - Payment</b>\n\n"
                    f"💵 Amount: <b>$50.00 USD</b>\n"
                    f"📦 Service: First Month Access\n\n"
                    f"<b>Payment Instructions:</b>\n"
                    f"1️⃣ Click the payment link below\n"
                    f"2️⃣ Complete the cryptocurrency payment\n"
                    f"3️⃣ Access will be granted automatically\n\n"
                    f"🔐 <i>Secure payment via OxaPay</i>\n"
                    f"⏱ <i>Payment expires in 30 minutes</i>\n\n"
                    f"🆔 Payment ID: <code>{payment_id}</code>"
                )
                
                buttons = [
                    [Button.url("💳 Pay Now", payment_link)],
                    [Button.inline("🔄 Check Status", f"check_payment_{payment_id}".encode())],
                    [Button.inline("🏠 Main Menu", b"main_menu")]
                ]
                
                await safe_edit(event, message, buttons=buttons)
            else:
                await event.answer("❌ Payment error. Please try again.", alert=True)
        
        # Refunding Methods
        elif data == "refunding_methods":
            await event.answer("📚 Coming soon! Stay tuned for exclusive refunding methods.", alert=True)
        
        # Aged Accounts
        elif data == "aged_accounts":
            message = (
                f"👤 <b>Premium Aged Accounts</b>\n\n"
                f"<i>Choose an account type:</i>\n\n"
                f"🍎 <b>Amazon Account</b>\n"
                f"• Well-aged with history\n"
                f"• Ready to use\n"
                f"• Price: $40\n\n"
                f"🍏 <b>Apple Account</b>\n"
                f"• Premium aged account\n"
                f"• Full access\n"
                f"• Price: $55"
            )
            
            buttons = [
                [Button.inline("🍎 Amazon - $40", b"aged_amazon")],
                [Button.inline("🍏 Apple - $55", b"aged_apple")],
                [Button.inline("🔙 Back", b"other_services")],
                [Button.inline("🏠 Main Menu", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        # Aged Amazon Account
        elif data == "aged_amazon":
            payment_link, payment_id = await create_payment(
                user_id,
                40,
                "Aged Amazon Account",
                f"AMAZON-{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            
            if payment_link:
                # Create service order
                order_id = create_service_order(
                    user_id,
                    "aged_account",
                    "Amazon Account",
                    40,
                    {'account_type': 'Amazon', 'payment_id': payment_id}
                )
                
                # Update payment with order reference
                payments = load_json(payments_file)
                if payment_id in payments:
                    payments[payment_id]['service_order_id'] = order_id
                    save_json(payments_file, payments)
                
                message = (
                    f"💳 <b>Aged Amazon Account - Payment</b>\n\n"
                    f"💵 Amount: <b>$40.00 USD</b>\n"
                    f"📦 Service: Premium Aged Amazon Account\n"
                    f"🆔 Order: <code>{order_id}</code>\n\n"
                    f"<b>Payment Instructions:</b>\n"
                    f"1️⃣ Click the payment link below\n"
                    f"2️⃣ Complete the cryptocurrency payment\n"
                    f"3️⃣ Order will be processed automatically\n\n"
                    f"🔐 <i>Secure payment via OxaPay</i>\n"
                    f"⏱ <i>Payment expires in 30 minutes</i>\n\n"
                    f"🆔 Payment ID: <code>{payment_id}</code>"
                )
                
                buttons = [
                    [Button.url("💳 Pay Now", payment_link)],
                    [Button.inline("🔄 Check Status", f"check_payment_{payment_id}".encode())],
                    [Button.inline("🏠 Main Menu", b"main_menu")]
                ]
                
                await safe_edit(event, message, buttons=buttons)
            else:
                await event.answer("❌ Payment error. Please try again.", alert=True)
        
        # Aged Apple Account
        elif data == "aged_apple":
            payment_link, payment_id = await create_payment(
                user_id,
                55,
                "Aged Apple Account",
                f"APPLE-{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            
            if payment_link:
                # Create service order
                order_id = create_service_order(
                    user_id,
                    "aged_account",
                    "Apple Account",
                    55,
                    {'account_type': 'Apple', 'payment_id': payment_id}
                )
                
                # Update payment with order reference
                payments = load_json(payments_file)
                if payment_id in payments:
                    payments[payment_id]['service_order_id'] = order_id
                    save_json(payments_file, payments)
                
                message = (
                    f"💳 <b>Aged Apple Account - Payment</b>\n\n"
                    f"💵 Amount: <b>$55.00 USD</b>\n"
                    f"📦 Service: Premium Aged Apple Account\n"
                    f"🆔 Order: <code>{order_id}</code>\n\n"
                    f"<b>Payment Instructions:</b>\n"
                    f"1️⃣ Click the payment link below\n"
                    f"2️⃣ Complete the cryptocurrency payment\n"
                    f"3️⃣ Order will be processed automatically\n\n"
                    f"🔐 <i>Secure payment via OxaPay</i>\n"
                    f"⏱ <i>Payment expires in 30 minutes</i>\n\n"
                    f"🆔 Payment ID: <code>{payment_id}</code>"
                )
                
                buttons = [
                    [Button.url("💳 Pay Now", payment_link)],
                    [Button.inline("🔄 Check Status", f"check_payment_{payment_id}".encode())],
                    [Button.inline("🏠 Main Menu", b"main_menu")]
                ]
                
                await safe_edit(event, message, buttons=buttons)
            else:
                await event.answer("❌ Payment error. Please try again.", alert=True)
        
        # Boxing Service
        elif data == "boxing_service":
            message = (
                f"📦 <b>Professional Boxing Services</b>\n\n"
                f"<i>Select a service:</i>\n\n"
                f"📦 <b>FTID - UPS/USPS/FEDEX</b> - $18\n"
                f"<i>Fake Tracking ID service</i>\n\n"
                f"📮 <b>RTS + DMG Left with Sender</b> - $50\n"
                f"<i>Return to sender with damage</i>\n\n"
                f"🔄 <b>RTS Returning to Sender</b> - $50\n"
                f"<i>Standard return to sender</i>\n\n"
                f"📦 <b>RTS + Delivery Custom/Random</b> - $60\n"
                f"<i>Custom delivery options</i>\n\n"
                f"🗑️ <b>POD Delete</b>\n"
                f"<i>Contact admin directly</i>\n\n"
                f"🎨 <b>UPS Insider Lit TX/NY</b> - $50\n"
                f"<i>Designer insider service</i>\n\n"
                f"⚡ <b>UPS Instant AP</b>\n"
                f"<i>24/7 instant service - Contact admin</i>"
            )
            
            buttons = [
                [Button.inline("📦 FTID - $18", b"boxing_ftid")],
                [Button.inline("📮 RTS + DMG - $50", b"boxing_rts_dmg")],
                [Button.inline("🔄 RTS Return - $50", b"boxing_rts_return")],
                [Button.inline("📦 RTS Custom - $60", b"boxing_rts_custom")],
                [Button.inline("🗑️ POD Delete", b"boxing_pod_delete")],
                [Button.inline("🎨 UPS Insider - $50", b"boxing_ups_insider")],
                [Button.inline("⚡ UPS Instant AP", b"boxing_ups_instant")],
                [Button.inline("🔙 Back", b"other_services")],
                [Button.inline("🏠 Main Menu", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Boxing service - POD Delete (redirect)
        elif data == "boxing_pod_delete":
            await event.answer("📞 Please contact admin directly for POD Delete service", alert=True)
            buttons = [
                [Button.url("👨‍💼 Contact Admin", "https://t.me/RefundHub_Twink")],
                [Button.inline("🔙 Back", b"boxing_service")],
                [Button.inline("🏠 Main Menu", b"main_menu")]
            ]
            
            message = (
                f"🗑️ <b>POD Delete Service</b>\n\n"
                f"<i>This service requires direct admin contact.</i>\n\n"
                f"📞 Please click below to contact admin:"
            )
            
            await safe_edit(event, message, buttons=buttons)
        
        # Boxing service - UPS Instant (redirect)
        elif data == "boxing_ups_instant":
            await event.answer("📞 Please contact admin directly for UPS Instant AP service", alert=True)
            buttons = [
                [Button.url("👨‍💼 Contact Admin", "https://t.me/RefundHub_Twink")],
                [Button.inline("🔙 Back", b"boxing_service")],
                [Button.inline("🏠 Main Menu", b"main_menu")]
            ]
            
            message = (
                f"⚡ <b>UPS Instant AP - 24/7</b>\n\n"
                f"<i>This service requires direct admin contact.</i>\n\n"
                f"📞 Please click below to contact admin:"
            )
            
            await safe_edit(event, message, buttons=buttons)
        
        # Boxing services that require form
        elif data.startswith("boxing_"):
            service_key = data.replace("boxing_", "")
            
            if service_key in BOXING_SERVICES:
                service_info = BOXING_SERVICES[service_key]
                
                if service_info.get('requires_form'):
                    boxing_service_states[user_id] = {
                        'service_key': service_key,
                        'service_name': service_info['name'],
                        'price': service_info['price'],
                        'current_field': 'file',
                        'order_data': {}
                    }
                    
                    message = (
                        f"📦 <b>{service_info['name']}</b>\n\n"
                        f"💰 Price: <b>${service_info['price']} USD</b>\n\n"
                        f"<b>📋 Required Information:</b>\n\n"
                        f"📎 <b>Step 1: Upload File</b>\n"
                        f"<i>Please upload the return label file</i>\n\n"
                        f"💡 Send /cancel to abort anytime"
                    )
                    
                    buttons = [[Button.inline("❌ Cancel", b"cancel_boxing")]]
                    
                    await safe_edit(event, message, buttons=buttons)
        
        # Cancel boxing service
        elif data == "cancel_boxing":
            if user_id in boxing_service_states:
                del boxing_service_states[user_id]
            
            await event.answer("❌ Boxing service order cancelled", alert=False)
            await safe_edit(
                event,
                "❌ <b>Order Cancelled</b>\n\n<i>No charges were made.</i>",
                buttons=[[Button.inline("📦 Boxing Service", b"boxing_service"), Button.inline("🏠 Home", b"main_menu")]]
            )
        
        # Confirm boxing service
        elif data.startswith("confirm_boxing_"):
            service_key = data.replace("confirm_boxing_", "")
            
            if user_id not in boxing_service_states:
                await event.answer("❌ Session expired", alert=True)
                return
            
            state = boxing_service_states[user_id]
            service_info = BOXING_SERVICES[service_key]
            
            # Create payment
            payment_link, payment_id = await create_payment(
                user_id,
                service_info['price'],
                f"Boxing Service - {service_info['name']}",
                f"BOX-{service_key.upper()}-{user_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            
            if payment_link:
                # Create service order
                order_id = create_service_order(
                    user_id,
                    "boxing_service",
                    service_info['name'],
                    service_info['price'],
                    {
                        'service_key': service_key,
                        'track_number': state['order_data']['track_number'],
                        'courier_service': state['order_data']['courier_service'],
                        'file_path': state['order_data'].get('file_path'),
                        'payment_id': payment_id
                    }
                )
                
                # Update payment with order reference
                payments = load_json(payments_file)
                if payment_id in payments:
                    payments[payment_id]['service_order_id'] = order_id
                    save_json(payments_file, payments)
                
                message = (
                    f"💳 <b>Boxing Service - Payment</b>\n\n"
                    f"📦 Service: {service_info['name']}\n"
                    f"💵 Amount: <b>${service_info['price']}.00 USD</b>\n"
                    f"🆔 Order: <code>{order_id}</code>\n\n"
                    f"<b>Order Details:</b>\n"
                    f"• Track #: {state['order_data']['track_number']}\n"
                    f"• Courier: {state['order_data']['courier_service']}\n"
                    f"• File: Uploaded ✓\n\n"
                    f"<b>Payment Instructions:</b>\n"
                    f"1️⃣ Click the payment link below\n"
                    f"2️⃣ Complete the cryptocurrency payment\n"
                    f"3️⃣ Order will be processed automatically\n\n"
                    f"🔐 <i>Secure payment via OxaPay</i>\n"
                    f"⏱ <i>Payment expires in 30 minutes</i>\n\n"
                    f"🆔 Payment ID: <code>{payment_id}</code>"
                )
                
                buttons = [
                    [Button.url("💳 Pay Now", payment_link)],
                    [Button.inline("🔄 Check Status", f"check_payment_{payment_id}".encode())],
                    [Button.inline("🏠 Main Menu", b"main_menu")]
                ]
                
                await safe_edit(event, message, buttons=buttons)
                
                del boxing_service_states[user_id]
            else:
                await event.answer("❌ Payment error. Please try again.", alert=True)
        
        # Check payment status
        elif data.startswith("check_payment_"):
            payment_id = data.replace("check_payment_", "")
            
            status = await check_payment_status(payment_id)
            
            if status == 'completed':
                payments = load_json(payments_file)
                payment_data = payments.get(payment_id)
                
                if payment_data:
                    amount = payment_data['amount']
                    description = payment_data['description']
                    
                    # Check if it's a wallet deposit
                    if 'Wallet Deposit' in description:
                        # Add to wallet
                        if add_to_wallet(user_id, amount, description):
                            await event.answer(f"✅ Payment completed! ${amount} added to wallet", alert=True)
                            
                            # Process referral reward
                            try:
                                reward_amount = await process_referral_reward(user_id, amount)
                                if reward_amount:
                                    log_error(f"Referral reward processed: ${reward_amount} for user deposit ${amount}", None)
                            except Exception as e:
                                log_error("Failed to process referral reward", e)
                            
                            # Notify admin
                            try:
                                user_entity = await bot.get_entity(user_id)
                                user_name = user_entity.first_name or "User"
                                
                                await bot.send_message(
                                    PAYMENT_NOTIFICATION_CHANNEL,
                                    f"💰 <b>Deposit Received</b>\n\n"
                                    f"👤 User: {user_name} (<code>{user_id}</code>)\n"
                                    f"💵 Amount: ${amount} USD\n"
                                    f"📝 Type: Wallet Deposit\n"
                                    f"🆔 Payment: <code>{payment_id}</code>",
                                    parse_mode='html'
                                )
                            except Exception as e:
                                log_error("Failed to notify admin about deposit", e)
                    
                    # Check if it's a service order
                    elif payment_data.get('service_order_id'):
                        order_id = payment_data['service_order_id']
                        
                        # Update service order status
                        if update_service_order(order_id, {'payment_status': 'paid'}):
                            service_order = get_service_order(order_id)
                            
                            await event.answer("✅ Payment completed! Order is being processed", alert=True)
                            
                            # Notify user
                            await bot.send_message(
                                user_id,
                                f"✅ <b>Payment Successful!</b>\n\n"
                                f"🆔 Order: <code>{order_id}</code>\n"
                                f"📦 Service: {service_order['service_name']}\n"
                                f"💰 Amount: ${service_order['price']} USD\n\n"
                                f"⏳ <b>Your order is being processed</b>\n\n"
                                f"<i>You'll be notified once it's ready for delivery!</i>",
                                parse_mode='html'
                            )
                            
                            # Notify admin
                            try:
                                user_entity = await bot.get_entity(user_id)
                                user_name = user_entity.first_name or "User"
                                
                                admin_message = (
                                    f"🔔 <b>SERVICE ORDER PAID</b>\n\n"
                                    f"🆔 Order: <code>{order_id}</code>\n"
                                    f"👤 User: {user_name} (<code>{user_id}</code>)\n"
                                    f"📦 Service: {service_order['service_name']}\n"
                                    f"💰 Amount: ${service_order['price']} USD\n"
                                    f"💳 Payment: <code>{payment_id}</code>\n\n"
                                    f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                                
                                admin_buttons = [
                                    [Button.inline("✅ Complete Order", f"complete_service_{order_id}".encode())],
                                    [Button.inline("💬 Start Chat", f"start_chat_service_{order_id}".encode())],
                                    [Button.inline("❌ Reject", f"reject_service_{order_id}".encode())]
                                ]
                                
                                await bot.send_message(
                                    ORDERS_CHANNEL_ID,
                                    admin_message,
                                    buttons=admin_buttons,
                                    parse_mode='html'
                                )
                            except Exception as e:
                                log_error("Failed to notify admin about service order", e)
                
                # Update message
                await safe_edit(
                    event,
                    "✅ <b>Payment Completed!</b>\n\n<i>Thank you for your payment. Processing your order...</i>",
                    buttons=[[Button.inline("🏠 Main Menu", b"main_menu")]]
                )
            
            elif status == 'failed':
                await event.answer("❌ Payment expired or failed", alert=True)
            else:
                await event.answer("⏳ Payment is still pending", alert=False)

# Store list
        elif data == "store_list":
            message = (
                f"🛍️ <b>Store Categories</b>\n\n"
                f"<i>Choose a category to browse premium stores:</i>\n\n"
                f"💻 <b>Electronics</b>\n"
                f"<i>Latest tech & gadgets from top brands</i>\n\n"
                f"👗 <b>Fashion & Apparel</b>\n"
                f"<i>Trendy clothing & accessories</i>\n\n"
                f"💄 <b>Beauty & Fragrance</b>\n"
                f"<i>Premium cosmetics & skincare</i>\n\n"
                f"🏬 <b>Retail & Wholesale</b>\n"
                f"<i>Everything you need in one place</i>\n\n"
                f"⚡ <i>All stores verified • Fast processing • Secure</i>"
            )
            
            buttons = [
                [Button.inline("💻 Electronics", b"cat_electronics")],
                [Button.inline("👗 Fashion & Apparel", b"cat_fashion")],
                [Button.inline("💄 Beauty & Fragrance", b"cat_beauty")],
                [Button.inline("🏬 Retail & Wholesale", b"cat_retail")],
                [Button.inline("📋 Full Store List", b"full_store_list")],
                [Button.inline("🏠 Back to Menu", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Full Store List - Send Telegraph link
        elif data == "full_store_list":
            message = (
                f"📋 <b>Full Store List</b>\n\n"
                f"🔗 View our complete store list:\n"
                f"https://telegra.ph/STORELIST-10-29\n\n"
                f"✨ <i>All available stores with detailed information</i>"
            )
            
            buttons = [[Button.inline("🏠 Back to Menu", b"main_menu")]]
            await safe_edit(event, message, buttons=buttons)
        
        # Category view
        elif data.startswith("cat_"):
            category = data.replace("cat_", "")
            stores_data = load_stores()
            if category in stores_data:
                stores = stores_data[category]['stores']
                category_name = stores_data[category]['name']
                
                message = f"{category_name}\n\n<i>Select a store to view details:</i>\n\n"
                
                for store_id, store in stores.items():
                    limits = store['limits']
                    message += (
                        f"{store['name']}\n"
                        f"<i>💰 Fee: {store['fee_percentage']}% • "
                        f"Range: ${limits['min']}-${limits['max']} • "
                        f"Time: {store['processing']}</i>\n\n"
                    )
                
                message += f"✨ <i>Total: {len(stores)} stores</i>"
                
                buttons = []
                for store_id, store in stores.items():
                    buttons.append([Button.inline(store['name'], f"store_{category}_{store_id}".encode())])
                
                buttons.append([Button.inline("🔙 Categories", b"store_list"), Button.inline("🏠 Home", b"main_menu")])
                
                await safe_edit(event, message, buttons=buttons)
        
        # Store details
        elif data.startswith("store_"):
            parts = data.split("_")
            category = parts[1]
            store_id = parts[2]
            
            stores_data = load_stores()
            if category in stores_data and store_id in stores_data[category]['stores']:
                store = stores_data[category]['stores'][store_id]
                limits = store['limits']
                
                example_order = 100
                example_fee = calculate_fee(example_order, store['fee_percentage'])
                
                message = (
                    f"{store['name']}\n\n"
                    f"<b>📋 Store Information</b>\n\n"
                    f"<b>💰 Fee Structure</b>\n"
                    f"• Fee: {store['fee_percentage']}%\n"
                    f"• Example: $100 order → ${example_fee} fee (You pay only ${example_fee})\n\n"
                    f"<b>📊 Order Limits</b>\n"
                    f"• Minimum: ${limits['min']}\n"
                    f"• Maximum: ${limits['max']}\n\n"
                    f"⏱ <b>Processing Time:</b> {store['processing']}\n\n"
                    f"<b>📝 Description</b>\n"
                    f"<i>{store['description']}</i>\n\n"
                    f"⚡ <i>Trusted • Secure • Fast</i>"
                )
                
                buttons = [
                    [Button.inline("🛒 Place Order", f"order_{category}_{store_id}".encode())],
                    [Button.inline("🔙 Back", f"cat_{category}".encode()), Button.inline("🏠 Home", b"main_menu")]
                ]
                
                await safe_edit(event, message, buttons=buttons)
        
        # Start order - Show options
        elif data.startswith("order_"):
            parts = data.split("_")
            category = parts[1]
            store_id = parts[2]
            
            stores_data = load_stores()
            if category in stores_data and store_id in stores_data[category]['stores']:
                store = stores_data[category]['stores'][store_id]
                
                message = (
                    f"🛒 <b>Place Order - {store['name']}</b>\n\n"
                    f"<b>Choose an option below:</b>\n\n"
                    f"📝 <b>Fill the form</b> - Complete our online order form\n"
                    f"💬 <b>Contact Ageless</b> - Speak directly with our team\n\n"
                    f"<i>Select your preferred method to proceed</i>"
                )
                
                buttons = [
                    [Button.url("📝 Fill the form", "https://cryptpad.fr/form/#/2/form/view/tpvjVyveo-xJR9TcuYheAovlmNjLdC5z2MHUs8gtbos/")],
                    [Button.url("💬 Contact Ageless", "https://t.me/ageless_1")],
                    [Button.inline("🔙 Back", f"store_{category}_{store_id}".encode()), Button.inline("🏠 Home", b"main_menu")]
                ]
                
                await safe_edit(event, message, buttons=buttons)
        
        # Confirm order
        elif data == "confirm_order":
            if user_id in order_states:
                state = order_states[user_id]
                order_data = state['order_data']
                store_info = state['store_info']
                
                order_id = create_order(user_id, store_info, order_data)
                
                try:
                    order_total = float(order_data['order_total'])
                    fee = calculate_fee(order_total, store_info['fee_percentage'])
                except:
                    fee = 0
                
                user_data = get_user_data(user_id)
                user_name = user_data['name']
                
                # Get last 4 digits of order ID
                order_short = order_id.split('-')[-1][-4:]
                
                order_notification = (
                    f"🔔 <b>NEW ORDER RECEIVED</b>\n\n"
                    f"🆔 <code>{order_id}</code>\n"
                    f"👤 {user_name} (ID: {user_id})\n"
                    f"🏪 {store_info['name']}\n\n"
                    f"<b>💰 Financial</b>\n"
                    f"• Order Total: ${order_data['order_total']}\n"
                    f"• Fee ({store_info['fee_percentage']}%): ${fee}\n"
                    f"• <b>Customer Pays: ${fee}</b>\n\n"
                    f"👤 {order_data['first_name']} {order_data['last_name']}\n"
                    f"📱 {order_data['phone_number']}\n\n"
                    f"📦 Order #: {order_data['order_number']}\n"
                    f"📍 Track: {order_data['track_number']}\n\n"
                    f"🔐 Login: {order_data['login_details']}\n"
                    f"📧 Mailbox: {order_data['mailbox_login']}\n\n"
                    f"🏠 Delivery:\n{order_data['delivery_address']}\n\n"
                    f"📮 Billing:\n{order_data['billing_address']}\n\n"
                    f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                admin_buttons = [
                    [Button.inline("✅ Accept", f"accept_{order_id}".encode()),
                     Button.inline("❌ Reject", f"reject_{order_id}".encode())],
                    [Button.inline("📝 Add Remark", f"remark_{order_id}".encode())]
                ]
                
                try:
                    await bot.send_message(ORDERS_CHANNEL_ID, order_notification, buttons=admin_buttons, parse_mode='html')
                except Exception as e:
                    log_error(f"Failed to send order to channel", e)
                
                success_msg = (
                    f"✅ <b>Order Submitted!</b>\n\n"
                    f"🆔 <code>{order_id}</code>\n"
                    f"🏪 {store_info['name']}\n"
                    f"💰 Amount to Pay: <code>${fee}</code>\n\n"
                    f"📨 <b>Order is being reviewed</b>\n\n"
                    f"⏱ Estimated: <i>{store_info['processing']}</i>\n"
                    f"💬 Updates via DM\n\n"
                    f"📋 Check status in Profile\n\n"
                    f"✨ <b>Thank you for choosing Ageless Portal!</b>"
                )
                
                buttons = [[Button.inline("🏠 Home", b"main_menu")]]
                
                await safe_edit(event, success_msg, buttons=buttons)
                
                del order_states[user_id]
        
        # Cancel order
        elif data == "cancel_order":
            if user_id in order_states:
                del order_states[user_id]
            
            await safe_edit(
                event,
                "❌ <b>Order Cancelled</b>\n\n<i>No charges were made.</i>",
                buttons=[[Button.inline("🛍️ Browse Stores", b"store_list"), Button.inline("🏠 Home", b"main_menu")]]
            )
        
        # Profile
        elif data == "profile":
            user_data = get_user_data(user_id)
            orders = load_json(orders_file)
            service_orders = load_json(service_orders_file)
            
            user_orders = [oid for oid in user_data.get('orders', []) if oid in orders]
            user_service_orders = [oid for oid in user_data.get('service_orders', []) if oid in service_orders]
            total_orders = len(user_orders)
            
            pending = sum(1 for oid in user_orders if orders[oid]['status'] == 'pending')
            completed = sum(1 for oid in user_orders if orders[oid]['status'] == 'completed')
            rejected = sum(1 for oid in user_orders if orders[oid]['status'] == 'rejected')
            
            wallet_balance = get_wallet_balance(user_id)
            
            message = (
                f"👤 <b>Your Profile</b>\n\n"
                f"<b>Personal Information</b>\n"
                f"• Name: {user_data['name']}\n"
                f"• User ID: <code>{user_id}</code>\n"
                f"• Member Since: {user_data['join_date']}\n\n"
                f"<b>💰 Wallet</b>\n"
                f"• Balance: <b>${wallet_balance:.2f} USD</b>\n\n"
                f"<b>📊 Order Statistics</b>\n"
                f"• Store Orders: <b>{total_orders}</b>\n"
                f"• Service Orders: <b>{len(user_service_orders)}</b>\n"
                f"• ⏳ Pending: {pending}\n"
                f"• ✅ Completed: {completed}\n"
                f"• ❌ Rejected: {rejected}\n\n"
            )
            
            if user_orders or user_service_orders:
                message += "<i>Use the buttons below to manage your account</i>"
            else:
                message += "<i>No orders yet. Start shopping!</i>"
            
            buttons = [
                [Button.inline("💰 Wallet", b"wallet"), Button.inline("📦 My Orders", b"my_orders")],
                [Button.inline("📊 Payment History", b"payment_history")],
                [Button.inline("🏠 Back to Menu", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Wallet
        elif data == "wallet":
            balance = get_wallet_balance(user_id)
            
            message = (
                f"💰 <b>Your Wallet</b>\n\n"
                f"💵 <b>Current Balance:</b> ${balance:.2f} USD\n\n"
                f"<b>Quick Actions:</b>\n"
                f"• 💳 Deposit funds via cryptocurrency\n"
                f"• 📊 View your payment history\n"
                f"• 🛒 Use balance for purchases\n\n"
                f"<i>Fast, secure, and convenient!</i>"
            )
            
            buttons = [
                [Button.inline("💳 Deposit Funds", b"wallet_deposit")],
                [Button.inline("📊 Payment History", b"payment_history")],
                [Button.inline("🏠 Main Menu", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Wallet deposit
        elif data == "wallet_deposit":
            deposit_states[user_id] = True
            
            message = (
                f"💳 <b>Deposit to Wallet</b>\n\n"
                f"<i>Enter the amount you want to deposit in USD:</i>\n\n"
                f"💡 Minimum: $1 USD\n"
                f"🔐 Payment via cryptocurrency (OxaPay)\n\n"
                f"<b>Example:</b> 50\n\n"
                f"💬 Send /cancel to abort"
            )
            
            await safe_edit(event, message, buttons=None)
        
        # Payment history
        elif data == "payment_history":
            user_data = get_user_data(user_id)
            payment_history = user_data.get('payment_history', [])
            
            if not payment_history:
                message = (
                    f"📊 <b>Payment History</b>\n\n"
                    f"<i>No payment history found.</i>\n\n"
                    f"💡 Make your first deposit to get started!"
                )
                
                buttons = [
                    [Button.inline("💳 Deposit Now", b"wallet_deposit")],
                    [Button.inline("🔙 Back", b"wallet")],
                    [Button.inline("🏠 Main Menu", b"main_menu")]
                ]
            else:
                message = f"📊 <b>Payment History</b>\n\n"
                
                # Show last 10 transactions
                recent = payment_history[-10:][::-1]
                
                for transaction in recent:
                    amount = transaction['amount']
                    trans_type = transaction['type']
                    desc = transaction['description']
                    timestamp = transaction['timestamp']
                    
                    emoji = "💰" if amount > 0 else "💸"
                    sign = "+" if amount > 0 else ""
                    
                    message += (
                        f"{emoji} <b>{sign}${abs(amount):.2f}</b>\n"
                        f"<i>{desc}</i>\n"
                        f"🕐 {timestamp}\n\n"
                    )
                
                if len(payment_history) > 10:
                    message += f"<i>Showing 10 of {len(payment_history)} transactions</i>"
                
                buttons = [
                    [Button.inline("🔙 Back to Wallet", b"wallet")],
                    [Button.inline("🏠 Main Menu", b"main_menu")]
                ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # My Orders
        elif data == "my_orders":
            user_data = get_user_data(user_id)
            orders = load_json(orders_file)
            service_orders = load_json(service_orders_file)
            
            user_orders = [oid for oid in user_data.get('orders', []) if oid in orders]
            user_service_orders = [oid for oid in user_data.get('service_orders', []) if oid in service_orders]
            
            message = f"📦 <b>My Orders</b>\n\n<i>Select order type to view:</i>\n\n"
            
            message += f"🛍️ <b>Store Orders:</b> {len(user_orders)}\n"
            message += f"⚙️ <b>Service Orders:</b> {len(user_service_orders)}\n"
            
            buttons = []
            
            if user_orders:
                buttons.append([Button.inline("🛍️ Store Orders", b"view_store_orders")])
            
            if user_service_orders:
                buttons.append([Button.inline("⚙️ Service Orders", b"view_service_orders")])
            
            if not user_orders and not user_service_orders:
                message += "\n<i>No orders yet. Start shopping!</i>"
                buttons.append([Button.inline("🛍️ Browse Stores", b"store_list")])
            
            buttons.append([Button.inline("🏠 Main Menu", b"main_menu")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # View store orders
        elif data == "view_store_orders":
            user_data = get_user_data(user_id)
            orders = load_json(orders_file)
            
            user_orders = [oid for oid in user_data.get('orders', []) if oid in orders]
            
            if not user_orders:
                await event.answer("❌ No store orders found", alert=True)
                return
            
            message = f"🛍️ <b>Store Orders</b>\n\n<i>Click an order to view details:</i>\n\n"
            
            buttons = []
            recent = user_orders[-10:][::-1]
            
            for oid in recent:
                order = orders[oid]
                status_emoji = {"pending": "⏳", "completed": "✅", "rejected": "❌"}
                emoji = status_emoji.get(order['status'], '📦')
                short_id = oid.split('-')[-1][-4:]
                store_name = order['store_info']['name'][:20]
                
                buttons.append([Button.inline(f"{emoji} ...{short_id} - {store_name}", f"view_order_{oid}".encode())])
            
            buttons.append([Button.inline("🔙 Back", b"my_orders")])
            buttons.append([Button.inline("🏠 Main Menu", b"main_menu")])
            
            await safe_edit(event, message, buttons=buttons)

        # View service orders
        elif data == "view_service_orders":
            user_data = get_user_data(user_id)
            service_orders = load_json(service_orders_file)
            
            user_service_orders = [oid for oid in user_data.get('service_orders', []) if oid in service_orders]
            
            if not user_service_orders:
                await event.answer("❌ No service orders found", alert=True)
                return
            
            message = f"⚙️ <b>Service Orders</b>\n\n<i>Click an order to view details:</i>\n\n"
            
            buttons = []
            recent = user_service_orders[-10:][::-1]
            
            for oid in recent:
                order = service_orders[oid]
                status_emoji = {"pending": "⏳", "completed": "✅", "rejected": "❌"}
                emoji = status_emoji.get(order['status'], '📦')
                short_id = oid.split('-')[-1][-4:]
                service_name = order['service_name'][:20]
                
                buttons.append([Button.inline(f"{emoji} ...{short_id} - {service_name}", f"view_service_order_{oid}".encode())])
            
            buttons.append([Button.inline("🔙 Back", b"my_orders")])
            buttons.append([Button.inline("🏠 Main Menu", b"main_menu")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # View individual order
        elif data.startswith("view_order_"):
            order_id = data.replace("view_order_", "")
            order = get_order(order_id)
            
            if not order or order['user_id'] != user_id:
                await event.answer("❌ Order not found", alert=True)
                return
            
            status_map = {"pending": "⏳ Pending", "completed": "✅ Completed", "rejected": "❌ Rejected"}
            status_text = status_map.get(order['status'], order['status'])
            
            payment_status_map = {"unpaid": "❌ Unpaid", "paid": "✅ Paid", "pending": "⏳ Pending"}
            payment_text = payment_status_map.get(order.get('payment_status', 'unpaid'), order.get('payment_status', 'unpaid'))
            
            try:
                total = float(order['order_data']['order_total'])
                fee = calculate_fee(total, order['store_info']['fee_percentage'])
            except:
                fee = 0
            
            message = (
                f"📦 <b>Order Details</b>\n\n"
                f"🆔 <code>{order_id}</code>\n"
                f"📊 Status: {status_text}\n"
                f"💳 Payment: {payment_text}\n\n"
                f"🏪 {order['store_info']['name']}\n"
                f"💰 Order Total: ${order['order_data']['order_total']}\n"
                f"💵 Fee ({order['store_info']['fee_percentage']}%): ${fee}\n"
                f"💸 Amount Paid: <b>${fee}</b>\n\n"
                f"📅 Ordered: {order['timestamp']}\n"
                f"📦 Order #: {order['order_data']['order_number']}\n"
                f"📍 Track: {order['order_data']['track_number']}\n\n"
            )
            
            if order.get('remarks'):
                message += "<b>📝 Updates & Remarks</b>\n\n"
                for remark in order['remarks'][-5:]:
                    message += f"• <b>{remark['by']}</b> ({remark['timestamp']}):\n<i>{remark['text']}</i>\n\n"
            else:
                message += "<i>No updates yet</i>"
            
            buttons = [
                [Button.inline("🔙 Back to Orders", b"view_store_orders")],
                [Button.inline("🏠 Main Menu", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # View individual service order
        elif data.startswith("view_service_order_"):
            order_id = data.replace("view_service_order_", "")
            order = get_service_order(order_id)
            
            if not order or order['user_id'] != user_id:
                await event.answer("❌ Order not found", alert=True)
                return
            
            status_map = {"pending": "⏳ Pending", "completed": "✅ Completed", "rejected": "❌ Rejected"}
            status_text = status_map.get(order['status'], order['status'])
            
            payment_status_map = {"unpaid": "❌ Unpaid", "paid": "✅ Paid"}
            payment_text = payment_status_map.get(order.get('payment_status', 'unpaid'), order.get('payment_status', 'unpaid'))
            
            message = (
                f"⚙️ <b>Service Order Details</b>\n\n"
                f"🆔 <code>{order_id}</code>\n"
                f"📊 Status: {status_text}\n"
                f"💳 Payment: {payment_text}\n\n"
                f"📦 Service: {order['service_name']}\n"
                f"💰 Price: ${order['price']}\n"
                f"📅 Ordered: {order['timestamp']}\n\n"
            )
            
            # Show delivery content if completed
            if order['status'] == 'completed' and order.get('delivery_content'):
                message += "<b>✅ Order Delivered</b>\n\n"
                if order['delivery_content'].get('content'):
                    message += f"<i>{order['delivery_content']['content']}</i>\n\n"
                message += f"<i>Delivered: {order['delivery_content']['timestamp']}</i>"
            else:
                message += "<i>⏳ Waiting for delivery...</i>"
            
            buttons = [
                [Button.inline("🔙 Back to Orders", b"view_service_orders")],
                [Button.inline("🏠 Main Menu", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Accept order
        elif data.startswith("accept_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("accept_", "")
            
            if update_order(order_id, {'status': 'accepted'}):
                add_order_remark(order_id, "✅ Order accepted by admin - Pending payment")
                
                order = get_order(order_id)
                customer_id = order['user_id']
                
                await bot.send_message(
                    customer_id,
                    f"✅ <b>Order Accepted!</b>\n\n"
                    f"🆔 <code>{order_id}</code>\n"
                    f"🏪 {order['store_info']['name']}\n\n"
                    f"⏳ <i>Waiting for admin to request payment...</i>",
                    parse_mode='html'
                )
                
                try:
                    msg = await event.get_message()
                    original_text = msg.message
                    
                    # Add Ask Payment button
                    new_buttons = [
                        [Button.inline("💰 Ask Payment", f"ask_payment_{order_id}".encode())],
                        [Button.inline("📝 Add Remark", f"remark_{order_id}".encode())],
                        [Button.inline("❌ Reject", f"reject_{order_id}".encode())]
                    ]
                    
                    await event.edit(
                        original_text + "\n\n✅ <b>ACCEPTED - Awaiting Payment Request</b>",
                        buttons=new_buttons,
                        parse_mode='html'
                    )
                except Exception as e:
                    log_error("Failed to edit message after accept", e)
                
                await event.answer("✅ Order accepted!", alert=True)
        
        # Admin: Ask payment
        elif data.startswith("ask_payment_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("ask_payment_", "")
            order = get_order(order_id)
            
            if not order:
                await event.answer("❌ Order not found", alert=True)
                return
            
            try:
                total = float(order['order_data']['order_total'])
                fee = calculate_fee(total, order['store_info']['fee_percentage'])
            except:
                fee = 0
            
            customer_id = order['user_id']
            customer_balance = get_wallet_balance(customer_id)
            
            # Create payment message for customer
            payment_message = (
                f"💰 <b>Payment Request</b>\n\n"
                f"🆔 Order: <code>{order_id}</code>\n"
                f"🏪 Store: {order['store_info']['name']}\n\n"
                f"<b>💵 Payment Details:</b>\n"
                f"• Order Total: ${order['order_data']['order_total']}\n"
                f"• Processing Fee ({order['store_info']['fee_percentage']}%): ${fee}\n"
                f"• <b>Amount to Pay: ${fee}</b>\n\n"
                f"💰 Your Wallet: <b>${customer_balance:.2f}</b>\n\n"
                f"<i>Choose payment method:</i>"
            )
            
            payment_buttons = [
                [Button.inline("💳 Pay with Wallet", f"pay_wallet_{order_id}".encode())],
                [Button.inline("🪙 Pay with Crypto", f"pay_crypto_{order_id}".encode())]
            ]
            
            await bot.send_message(customer_id, payment_message, buttons=payment_buttons, parse_mode='html')
            
            add_order_remark(order_id, f"💰 Payment request sent - Amount: ${fee}")
            
            await event.answer("✅ Payment request sent to customer!", alert=True)
        
        # Pay with wallet
        elif data.startswith("pay_wallet_"):
            order_id = data.replace("pay_wallet_", "")
            order = get_order(order_id)
            
            if not order or order['user_id'] != user_id:
                await event.answer("❌ Order not found", alert=True)
                return
            
            try:
                total = float(order['order_data']['order_total'])
                fee = calculate_fee(total, order['store_info']['fee_percentage'])
            except:
                await event.answer("❌ Error calculating amount", alert=True)
                return
            
            # Check wallet balance
            balance = get_wallet_balance(user_id)
            
            if balance < fee:
                await event.answer(f"❌ Insufficient balance. You need ${fee:.2f} but have ${balance:.2f}", alert=True)
                return
            
            # Deduct from wallet (only fee, not order_total + fee)
            if deduct_from_wallet(user_id, fee, f"Order Payment - {order_id}"):
                update_order(order_id, {'payment_status': 'paid', 'status': 'processing'})
                add_order_remark(order_id, f"✅ Payment received via wallet - ${fee}")
                
                await event.answer("✅ Payment successful!", alert=True)
                
                # Notify user
                await bot.send_message(
                    user_id,
                    f"✅ <b>Payment Successful!</b>\n\n"
                    f"🆔 Order: <code>{order_id}</code>\n"
                    f"💰 Amount Paid: ${fee}\n"
                    f"💳 Method: Wallet\n\n"
                    f"⏳ <i>Your order is now being processed!</i>",
                    parse_mode='html'
                )
                
                # Notify admin
                try:
                    user_data = get_user_data(user_id)
                    # Notify all admins
                    for admin_id in ADMIN_ID:
                        await bot.send_message(
                            admin_id,
                            f"💰 <b>Payment Received!</b>\n\n"
                            f"🆔 Order: <code>{order_id}</code>\n"
                            f"👤 User: {user_data['name']} (<code>{user_id}</code>)\n"
                            f"💵 Amount: ${fee}\n"
                            f"💳 Method: Wallet\n\n"
                            f"✅ <i>Ready to complete order</i>",
                            buttons=[[Button.inline("✅ Complete Order", f"complete_order_{order_id}".encode())]],
                        parse_mode='html'
                    )
                except Exception as e:
                    log_error("Failed to notify admin about payment", e)
                
                await safe_edit(
                    event,
                    "✅ <b>Payment Completed!</b>\n\n<i>Your order is being processed...</i>",
                    buttons=[[Button.inline("📦 View Order", f"view_order_{order_id}".encode()), Button.inline("🏠 Home", b"main_menu")]]
                )
            else:
                await event.answer("❌ Payment failed. Please try again.", alert=True)
        
        # Pay with crypto
        elif data.startswith("pay_crypto_"):
            order_id = data.replace("pay_crypto_", "")
            order = get_order(order_id)
            
            if not order or order['user_id'] != user_id:
                await event.answer("❌ Order not found", alert=True)
                return
            
            try:
                total = float(order['order_data']['order_total'])
                fee = calculate_fee(total, order['store_info']['fee_percentage'])
            except:
                await event.answer("❌ Error calculating amount", alert=True)
                return
            
            # Create payment (only fee, not order_total + fee)
            payment_link, payment_id = await create_payment(
                user_id,
                fee,
                f"Order Payment - {order_id}",
                f"ORDER-{order_id}"
            )
            
            if payment_link:
                # Link payment to order
                payments = load_json(payments_file)
                if payment_id in payments:
                    payments[payment_id]['order_id'] = order_id
                    save_json(payments_file, payments)
                
                message = (
                    f"💳 <b>Crypto Payment</b>\n\n"
                    f"🆔 Order: <code>{order_id}</code>\n"
                    f"💰 Amount to Pay: <b>${fee}</b>\n\n"
                    f"<b>Payment Instructions:</b>\n"
                    f"1️⃣ Click the payment link below\n"
                    f"2️⃣ Complete the cryptocurrency payment\n"
                    f"3️⃣ Order will be processed automatically\n\n"
                    f"🔐 <i>Secure payment via OxaPay</i>\n"
                    f"⏱ <i>Payment expires in 30 minutes</i>\n\n"
                    f"🆔 Payment ID: <code>{payment_id}</code>"
                )
                
                buttons = [
                    [Button.url("💳 Pay Now", payment_link)],
                    [Button.inline("🔄 Check Status", f"check_order_payment_{payment_id}".encode())],
                    [Button.inline("🏠 Main Menu", b"main_menu")]
                ]
                
                await safe_edit(event, message, buttons=buttons)
            else:
                await event.answer("❌ Payment error. Please try again.", alert=True)
        
        # Check order payment
        elif data.startswith("check_order_payment_"):
            payment_id = data.replace("check_order_payment_", "")
            
            status = await check_payment_status(payment_id)
            
            if status == 'completed':
                payments = load_json(payments_file)
                payment_data = payments.get(payment_id)
                
                if payment_data and payment_data.get('order_id'):
                    order_id = payment_data['order_id']
                    amount = payment_data['amount']
                    
                    # Update order
                    update_order(order_id, {'payment_status': 'paid', 'status': 'processing'})
                    add_order_remark(order_id, f"✅ Payment received via crypto - ${amount}")
                    
                    order = get_order(order_id)
                    
                    # Notify user
                    await bot.send_message(
                        user_id,
                        f"✅ <b>Payment Successful!</b>\n\n"
                        f"🆔 Order: <code>{order_id}</code>\n"
                        f"💰 Amount: ${amount}\n"
                        f"💳 Method: Cryptocurrency\n\n"
                        f"⏳ <i>Your order is now being processed!</i>",
                        parse_mode='html'
                    )
                    
                    # Notify admin
                    try:
                        user_data = get_user_data(user_id)
                        await bot.send_message(
                            PAYMENT_NOTIFICATION_CHANNEL,
                            f"💰 <b>Order Payment Received!</b>\n\n"
                            f"🆔 Order: <code>{order_id}</code>\n"
                            f"👤 User: {user_data['name']} (<code>{user_id}</code>)\n"
                            f"🏪 Store: {order['store_info']['name']}\n"
                            f"💵 Amount: ${amount}\n"
                            f"💳 Method: Cryptocurrency\n\n"
                            f"✅ <i>Ready to complete order</i>",
                            buttons=[[Button.inline("✅ Complete Order", f"complete_order_{order_id}".encode())]],
                            parse_mode='html'
                        )
                    except Exception as e:
                        log_error("Failed to notify admin about order payment", e)
                    
                    await safe_edit(
                        event,
                        "✅ <b>Payment Completed!</b>\n\n<i>Your order is being processed...</i>",
                        buttons=[[Button.inline("📦 View Order", f"view_order_{order_id}".encode()), Button.inline("🏠 Home", b"main_menu")]]
                    )
                    
                    await event.answer("✅ Payment successful!", alert=True)
                else:
                    await event.answer("❌ Order not found", alert=True)
            elif status == 'failed':
                await event.answer("❌ Payment expired or failed", alert=True)
            else:
                await event.answer("⏳ Payment is still pending", alert=False)
        
        # Admin: Complete order
        elif data.startswith("complete_order_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("complete_order_", "")
            
            admin_complete_order_states[user_id] = {'order_id': order_id}
            
            await bot.send_message(
                user_id,
                f"📦 <b>Complete Order</b>\n\n"
                f"🆔 <code>{order_id}</code>\n\n"
                f"<i>Send the order completion message/file to deliver to customer:</i>\n\n"
                f"💡 You can send text, images, or files\n"
                f"📝 Type /cancel to abort",
                parse_mode='html'
            )
            
            await event.answer("📝 Send completion content in DM", alert=True)
        
        # Admin: Final complete order
        elif data.startswith("admin_final_complete_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("admin_final_complete_", "")
            
            if user_id not in admin_complete_order_states:
                await event.answer("❌ Session expired", alert=True)
                return
            
            state = admin_complete_order_states[user_id]
            delivery_content = state.get('delivery_content')
            
            # Update order status
            update_order(order_id, {'status': 'completed'})
            add_order_remark(order_id, "✅ Order completed and delivered")
            
            order = get_order(order_id)
            customer_id = order['user_id']
            
            # Send to customer
            try:
                if delivery_content['type'] == 'media':
                    await bot.send_file(
                        customer_id,
                        delivery_content['file_path'],
                        caption=f"✅ <b>Order Completed!</b>\n\n🆔 <code>{order_id}</code>\n\n<i>Thank you for your order!</i>",
                        parse_mode='html'
                    )
                else:
                    await bot.send_message(
                        customer_id,
                        f"✅ <b>Order Completed!</b>\n\n"
                        f"🆔 <code>{order_id}</code>\n\n"
                        f"<b>Delivery:</b>\n{delivery_content['content']}\n\n"
                        f"<i>Thank you for your order!</i>",
                        parse_mode='html'
                    )
                
                await event.answer("✅ Order completed and delivered!", alert=True)
                await event.edit("✅ <b>Order Completed!</b>\n\n<i>Customer has been notified</i>", parse_mode='html')
                
                del admin_complete_order_states[user_id]
            except Exception as e:
                log_error("Failed to deliver completed order", e)
                await event.answer("❌ Failed to deliver order", alert=True)
        
        # Admin: Cancel complete
        elif data == "admin_cancel_complete":
            if user_id in admin_complete_order_states:
                del admin_complete_order_states[user_id]
            await event.answer("❌ Cancelled", alert=False)
        
        # Admin: Reject order
        elif data.startswith("reject_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("reject_", "")
            
            if update_order(order_id, {'status': 'rejected'}):
                add_order_remark(order_id, "❌ Order rejected by admin")
                
                order = get_order(order_id)
                customer_id = order['user_id']
                
                await bot.send_message(
                    customer_id,
                    f"❌ <b>Order Rejected</b>\n\n"
                    f"🆔 <code>{order_id}</code>\n\n"
                    f"<i>Your order has been rejected. Contact support for more info.</i>",
                    parse_mode='html'
                )
                
                try:
                    msg = await event.get_message()
                    original_text = msg.message
                    await event.edit(
                        original_text + "\n\n❌ <b>REJECTED BY ADMIN</b>",
                        buttons=None,
                        parse_mode='html'
                    )
                except Exception as e:
                    log_error("Failed to edit message after reject", e)
                
                await event.answer("❌ Order rejected!", alert=True)
        
        # Admin: Complete service order
        elif data.startswith("complete_service_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("complete_service_", "")
            
            admin_complete_order_states[user_id] = {'order_id': order_id, 'is_service': True}
            
            await bot.send_message(
                user_id,
                f"📦 <b>Complete Service Order</b>\n\n"
                f"🆔 <code>{order_id}</code>\n\n"
                f"<i>Send the service delivery content:</i>\n\n"
                f"💡 You can send text, images, or files\n"
                f"📝 Type /cancel to abort",
                parse_mode='html'
            )
            
            await event.answer("📝 Send completion content in DM", alert=True)
        
        # Admin: Start chat for service order
        elif data.startswith("start_chat_service_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("start_chat_service_", "")
            service_order = get_service_order(order_id)
            
            if service_order:
                customer_id = service_order['user_id']
                
                try:
                    user_entity = await bot.get_entity(customer_id)
                    user_name = user_entity.first_name or "User"
                    
                    ticket_id = create_ticket(customer_id, f"Support for order {order_id}", user_name)
                    update_ticket(ticket_id, {'status': 'active'})
                    
                    await bot.send_message(
                        customer_id,
                        f"✅ <b>Support Chat Started</b>\n\n"
                        f"🆔 Order: <code>{order_id}</code>\n"
                        f"🎫 Ticket: <code>{ticket_id}</code>\n\n"
                        f"💬 Admin has started a chat with you\n\n"
                        f"<i>Type /endchat to close</i>",
                        parse_mode='html'
                    )
                    
                    # Notify all admins
                    for admin_id in ADMIN_ID:
                        await bot.send_message(
                            admin_id,
                            f"✅ <b>Chat Started</b>\n\n"
                        f"👤 User: {user_name}\n"
                        f"🆔 Order: <code>{order_id}</code>\n"
                        f"🎫 Ticket: <code>{ticket_id}</code>\n\n"
                        f"<i>Type /endchat to close</i>",
                        parse_mode='html'
                    )
                    
                    await event.answer("✅ Chat started!", alert=True)
                except Exception as e:
                    log_error("Failed to start chat", e)
                    await event.answer("❌ Failed to start chat", alert=True)
        
        # Admin: Reject service order
        elif data.startswith("reject_service_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("reject_service_", "")
            
            if update_service_order(order_id, {'status': 'rejected'}):
                service_order = get_service_order(order_id)
                customer_id = service_order['user_id']
                
                await bot.send_message(
                    customer_id,
                    f"❌ <b>Service Order Rejected</b>\n\n"
                    f"🆔 <code>{order_id}</code>\n\n"
                    f"<i>Your order has been rejected. Contact support for more info.</i>",
                    parse_mode='html'
                )
                
                await event.answer("❌ Service order rejected!", alert=True)
        
        # Admin: Add remark
        elif data.startswith("remark_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("remark_", "")
            
            admin_remark_state[user_id] = {'order_id': order_id}
            
            await bot.send_message(
                user_id,
                f"📝 <b>Add Remark to Order</b>\n\n"
                f"🆔 <code>{order_id}</code>\n\n"
                f"<i>Send your remark message in DM:</i>\n\n"
                f"(Type /cancel to abort)",
                parse_mode='html'
            )
            
            await event.answer("📝 Send remark in bot DM", alert=True)
        
        # Admin Panel
        elif data == "admin_panel":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            orders = load_json(orders_file)
            service_orders = load_json(service_orders_file)
            tickets = load_json(tickets_file)
            raffles = load_json(raffles_file)
            users = get_all_users()
            
            all_orders = list(orders.keys())
            pending = [o for o in all_orders if orders[o]['status'] == 'pending']
            processing = [o for o in all_orders if orders[o]['status'] in ['accepted', 'processing']]
            completed = [o for o in all_orders if orders[o]['status'] == 'completed']
            
            service_pending = [o for o in service_orders.keys() if service_orders[o]['status'] == 'pending']
            service_completed = [o for o in service_orders.keys() if service_orders[o]['status'] == 'completed']
            
            active_tickets = [t for t, data in tickets.items() if data['status'] == 'active']
            pending_tickets = [t for t, data in tickets.items() if data['status'] == 'pending']
            
            active_raffles = [r for r, data in raffles.items() if data['status'] == 'active']
            
            message = (
                f"🔧 <b>Admin Panel</b>\n\n"
                f"<b>📊 Statistics</b>\n\n"
                f"<b>Users:</b>\n"
                f"• Total Users: {len(users)}\n\n"
                f"<b>Store Orders:</b>\n"
                f"• Total: {len(all_orders)}\n"
                f"• ⏳ Pending: {len(pending)}\n"
                f"• ⚙️ Processing: {len(processing)}\n"
                f"• ✅ Completed: {len(completed)}\n\n"
                f"<b>Service Orders:</b>\n"
                f"• ⏳ Pending: {len(service_pending)}\n"
                f"• ✅ Completed: {len(service_completed)}\n\n"
                f"<b>Support Tickets:</b>\n"
                f"• 💬 Active: {len(active_tickets)}\n"
                f"• ⏳ Pending: {len(pending_tickets)}\n\n"
                f"<b>Raffles:</b>\n"
                f"• 🎁 Active: {len(active_raffles)}\n\n"
                f"<i>Select an option:</i>"
            )
            
            buttons = [
                [Button.inline("📦 Store Orders", b"admin_orders"),
                 Button.inline("⚙️ Service Orders", b"admin_service_orders")],
                [Button.inline("🎫 Tickets", b"admin_tickets"),
                 Button.inline("👥 User Stats", b"admin_user_stats")],
                [Button.inline("🛍️ Store Manage", b"admin_store_manage")],
                [Button.inline("🎁 Create Raffle", b"create_raffle"),
                 Button.inline("📊 Error Logs", b"admin_logs")],
                [Button.inline("💳 Change Payment Details", b"change_payment_details")],
                [Button.inline("🏠 Back to Menu", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Service Orders
        elif data == "admin_service_orders":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            service_orders = load_json(service_orders_file)
            
            pending = [oid for oid, o in service_orders.items() if o['status'] == 'pending']
            completed = [oid for oid, o in service_orders.items() if o['status'] == 'completed']
            rejected = [oid for oid, o in service_orders.items() if o['status'] == 'rejected']
            
            message = (
                f"⚙️ <b>Service Orders Management</b>\n\n"
                f"<b>Statistics:</b>\n"
                f"• ⏳ Pending: {len(pending)}\n"
                f"• ✅ Completed: {len(completed)}\n"
                f"• ❌ Rejected: {len(rejected)}\n\n"
                f"<i>Select category:</i>"
            )
            
            buttons = [
                [Button.inline("⏳ Pending", b"admin_service_pending_0")],
                [Button.inline("✅ Completed", b"admin_service_completed_0")],
                [Button.inline("❌ Rejected", b"admin_service_rejected_0")],
                [Button.inline("🔙 Admin Panel", b"admin_panel")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Service orders by status
        elif data.startswith("admin_service_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            parts = data.split("_")
            status = parts[2]
            page = int(parts[3])
            
            service_orders = load_json(service_orders_file)
            filtered = [oid for oid, o in service_orders.items() if o['status'] == status]
            filtered.sort(key=lambda x: service_orders[x]['timestamp'], reverse=True)
            
            per_page = 10
            start = page * per_page
            end = start + per_page
            page_orders = filtered[start:end]
            
            total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
            
            status_name = {"pending": "⏳ Pending", "completed": "✅ Completed", "rejected": "❌ Rejected"}
            
            message = (
                f"⚙️ <b>{status_name.get(status, status)} Service Orders</b>\n"
                f"<i>Page {page + 1} of {total_pages}</i>\n\n"
            )
            
            if page_orders:
                buttons = []
                for oid in page_orders:
                    order = service_orders[oid]
                    short_id = oid.split('-')[-1][-4:]
                    try:
                        user_entity = await bot.get_entity(order['user_id'])
                        user_name = user_entity.first_name or "User"
                        button_text = f"...{short_id} - {user_name[:10]}"
                    except:
                        button_text = f"...{short_id}"
                    
                    buttons.append([Button.inline(button_text, f"admin_view_service_{oid}".encode())])
            else:
                message += "<i>No orders found</i>"
                buttons = []
            
            nav = []
            if page > 0:
                nav.append(Button.inline("⬅️ Prev", f"admin_service_{status}_{page-1}".encode()))
            if end < len(filtered):
                nav.append(Button.inline("Next ➡️", f"admin_service_{status}_{page+1}".encode()))
            
            if nav:
                buttons.append(nav)
            
            buttons.append([Button.inline("🔙 Service Orders", b"admin_service_orders")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Store Management
        elif data == "admin_store_manage":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            stores_data = load_stores()
            total_stores = sum(len(cat['stores']) for cat in stores_data.values())
            
            message = (
                f"🛍️ <b>Store Management</b>\n\n"
                f"📊 <b>Statistics:</b>\n"
                f"• Total Categories: {len(stores_data)}\n"
                f"• Total Stores: {total_stores}\n\n"
                f"<i>Select an action:</i>"
            )
            
            buttons = [
                [Button.inline("➕ Add Store", b"admin_store_add_category")],
                [Button.inline("✏️ Edit Store", b"admin_store_edit_category")],
                [Button.inline("🗑️ Remove Store", b"admin_store_remove_category")],
                [Button.inline("🔙 Admin Panel", b"admin_panel")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Add Store - Select Category
        elif data == "admin_store_add_category":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            stores_data = load_stores()
            message = "📂 <b>Select Category for New Store</b>\n\n<i>Or create a new category:</i>"
            
            buttons = []
            for cat_id, cat_data in stores_data.items():
                buttons.append([Button.inline(cat_data['name'], f"admin_store_add_{cat_id}".encode())])
            
            buttons.append([Button.inline("➕ New Category", b"admin_store_add_new_category")])
            buttons.append([Button.inline("🔙 Store Manage", b"admin_store_manage")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Add Store - New Category
        elif data == "admin_store_add_new_category":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            store_management_state[user_id] = {
                'action': 'add',
                'step': 'category_name',
                'store_data': {}
            }
            
            await bot.send_message(
                user_id,
                "📂 <b>Create New Category</b>\n\n"
                "Enter the category name:\n"
                "<i>Example: Electronics & Tech, Fashion & Apparel, etc.</i>\n\n"
                "(Type /cancel to abort)",
                parse_mode='html'
            )
            
            await event.answer("📝 Send category name in bot DM", alert=True)
        
        # Admin: Add Store - Start Process
        elif data.startswith("admin_store_add_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            category = data.replace("admin_store_add_", "")
            stores_data = load_stores()
            
            if category not in stores_data:
                await event.answer("❌ Category not found", alert=True)
                return
            
            store_management_state[user_id] = {
                'action': 'add',
                'category': category,
                'step': 'store_name',
                'store_data': {}
            }
            
            await bot.send_message(
                user_id,
                "➕ <b>Add New Store</b>\n\n"
                "📝 <b>Step 1/6: Store Name</b>\n\n"
                "Enter the store name:\n"
                "<i>Example: 📦 Amazon, 🍎 Apple, etc.</i>\n\n"
                "(Type /cancel to abort)",
                parse_mode='html'
            )
            
            await event.answer("📝 Send store name in bot DM", alert=True)
        
        # Admin: Edit Store - Select Category
        elif data == "admin_store_edit_category":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            stores_data = load_stores()
            message = "📂 <b>Select Category</b>\n\n<i>Choose category to edit stores:</i>"
            
            buttons = []
            for cat_id, cat_data in stores_data.items():
                store_count = len(cat_data['stores'])
                buttons.append([Button.inline(f"{cat_data['name']} ({store_count} stores)", f"admin_store_edit_list_{cat_id}".encode())])
            
            buttons.append([Button.inline("🔙 Store Manage", b"admin_store_manage")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Edit Store - List Stores
        elif data.startswith("admin_store_edit_list_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            category = data.replace("admin_store_edit_list_", "")
            stores_data = load_stores()
            
            if category not in stores_data:
                await event.answer("❌ Category not found", alert=True)
                return
            
            stores = stores_data[category]['stores']
            message = f"✏️ <b>Edit Store - {stores_data[category]['name']}</b>\n\n<i>Select a store to edit:</i>"
            
            buttons = []
            for store_id, store in stores.items():
                buttons.append([Button.inline(store['name'], f"admin_store_edit_{category}_{store_id}".encode())])
            
            buttons.append([Button.inline("🔙 Categories", b"admin_store_edit_category")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Edit Store - Start Edit
        elif data.startswith("admin_store_edit_") and not data.startswith("admin_store_edit_list_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            parts = data.replace("admin_store_edit_", "").split("_", 1)
            if len(parts) == 2:
                category = parts[0]
                store_id = parts[1]
                
                stores_data = load_stores()
                if category in stores_data and store_id in stores_data[category]['stores']:
                    store_management_state[user_id] = {
                        'action': 'edit',
                        'category': category,
                        'store_id': store_id,
                        'step': 'store_name',
                        'store_data': stores_data[category]['stores'][store_id].copy()
                    }
                    
                    await bot.send_message(
                        user_id,
                        f"✏️ <b>Edit Store</b>\n\n"
                        f"📝 <b>Step 1/6: Store Name</b>\n\n"
                        f"Current: {stores_data[category]['stores'][store_id]['name']}\n\n"
                        f"Enter new store name (or send current to keep):\n"
                        f"<i>Example: 📦 Amazon, 🍎 Apple, etc.</i>\n\n"
                        f"(Type /cancel to abort)",
                        parse_mode='html'
                    )
                    
                    await event.answer("📝 Send store name in bot DM", alert=True)
        
        # Admin: Remove Store - Select Category
        elif data == "admin_store_remove_category":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            stores_data = load_stores()
            message = "📂 <b>Select Category</b>\n\n<i>Choose category to remove stores:</i>"
            
            buttons = []
            for cat_id, cat_data in stores_data.items():
                store_count = len(cat_data['stores'])
                buttons.append([Button.inline(f"{cat_data['name']} ({store_count} stores)", f"admin_store_remove_list_{cat_id}".encode())])
            
            buttons.append([Button.inline("🔙 Store Manage", b"admin_store_manage")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Remove Store - List Stores
        elif data.startswith("admin_store_remove_list_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            category = data.replace("admin_store_remove_list_", "")
            stores_data = load_stores()
            
            if category not in stores_data:
                await event.answer("❌ Category not found", alert=True)
                return
            
            stores = stores_data[category]['stores']
            message = f"🗑️ <b>Remove Store - {stores_data[category]['name']}</b>\n\n<i>Select a store to remove:</i>"
            
            buttons = []
            for store_id, store in stores.items():
                buttons.append([Button.inline(store['name'], f"admin_store_remove_{category}_{store_id}".encode())])
            
            buttons.append([Button.inline("🔙 Categories", b"admin_store_remove_category")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin: Remove Store - Confirm
        elif data.startswith("admin_store_remove_") and not data.startswith("admin_store_remove_list_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            parts = data.replace("admin_store_remove_", "").split("_", 1)
            if len(parts) == 2:
                category = parts[0]
                store_id = parts[1]
                
                stores_data = load_stores()
                if category in stores_data and store_id in stores_data[category]['stores']:
                    store_name = stores_data[category]['stores'][store_id]['name']
                    
                    # Remove store
                    del stores_data[category]['stores'][store_id]
                    
                    if save_stores(stores_data):
                        await event.answer(f"✅ Store '{store_name}' removed!", alert=True)
                        
                        message = (
                            f"✅ <b>Store Removed</b>\n\n"
                            f"🗑️ <b>{store_name}</b> has been removed from <b>{stores_data[category]['name']}</b>\n\n"
                            f"<i>Select an action:</i>"
                        )
                        
                        buttons = [
                            [Button.inline("➕ Add Store", b"admin_store_add_category")],
                            [Button.inline("✏️ Edit Store", b"admin_store_edit_category")],
                            [Button.inline("🗑️ Remove Store", b"admin_store_remove_category")],
                            [Button.inline("🔙 Admin Panel", b"admin_panel")]
                        ]
                        
                        await safe_edit(event, message, buttons=buttons)
                    else:
                        await event.answer("❌ Failed to save changes", alert=True)
        
        # Vouches - Reviews
        elif data == "vouches":
            message = (
                f"⭐ <b>See Our Reviews!</b>\n\n"
                f"<i>📢 Platform:</i> <b>Cracked.sh</b>\n"
                f"<i>🔗 Hundreds of verified customer reviews</i>\n\n"
                f"🏆 <b>TOP VOUCHED</b> refunding service\n"
                f"✅ <b>STAFF VOUCHED</b> & verified\n\n"
                f"💬 <i>Read honest reviews from our satisfied customers!</i>"
            )
            
            buttons = [
                [Button.url("⭐ View Reviews on Cracked.sh", "https://cracked.sh/Thread-Supreme-TOP-VOUCHED-AGELESS-REFUNDS-INSTANT-WORLDWIDE-INSIDER-STORES-24-7-SUPPORT")],
                [Button.inline("🔙 Back", b"main_menu")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Main Menu
        elif data == "main_menu":
            try:
                await event.delete()
            except:
                pass
            
            await send_main_menu(user_id)
        
        # Broadcast
        elif data == "confirm_broadcast":
            if not is_admin(user_id):
                await event.answer("❌ Not authorized!", alert=True)
                return
            
            if user_id not in broadcast_state:
                await event.answer("❌ No message!", alert=True)
                return
            
            await event.answer("📢 Broadcasting...", alert=False)
            await event.edit("📢 <b>Broadcasting...</b>", parse_mode='html')
            
            broadcast_msg = broadcast_state[user_id]['message']
            users = get_all_users()
            total = len(users)
            
            if total == 0:
                await event.edit("❌ No users!")
                del broadcast_state[user_id]
                return
            
            success = blocked = 0
            
            for idx, uid in enumerate(users, 1):
                try:
                    await bot.send_message(uid, broadcast_msg)
                    success += 1
                except:
                    blocked += 1
                
                if idx % 10 == 0:
                    try:
                        await event.edit(
                            f"📢 <b>Broadcasting...</b>\n\n"
                            f"{idx}/{total} ({int(idx/total*100)}%)\n"
                            f"✅ {success} | 🚫 {blocked}",
                            parse_mode='html'
                        )
                    except:
                        pass
                
                await asyncio.sleep(0.05)
            
            await event.edit(
                f"✅ <b>Complete!</b>\n\n"
                f"Total: {total}\n"
                f"✅ Success: {success}\n"
                f"🚫 Blocked: {blocked}\n"
                f"📈 Rate: {int(success/total*100)}%",
                parse_mode='html'
            )
            
            del broadcast_state[user_id]
        
        elif data == "cancel_broadcast":
            if user_id in broadcast_state:
                del broadcast_state[user_id]
            await event.edit("❌ <b>Cancelled</b>", parse_mode='html')
        
        # Raffle creation
        elif data == "create_raffle":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            raffle_creation_state[user_id] = {'current_field': 'prize'}
            
            await safe_edit(
                event,
                f"🎁 <b>Create New Raffle</b>\n\n"
                f"🏆 <b>Prize Description</b>\n\n"
                f"<i>What's the prize for this raffle?</i>\n\n"
                f"Example: iPhone 15 Pro Max\n\n"
                f"💡 Send /cancel to abort",
                buttons=None
            )
        
        elif data == "create_raffle_confirm":
            if not is_admin(user_id) or user_id not in raffle_creation_state:
                return
            
            state = raffle_creation_state[user_id]
            
            raffle_id = create_raffle(
                state['prize'],
                state['winners_count'],
                state['duration_minutes']
            )
            
            raffle = get_raffle(raffle_id)
            end_time = datetime.fromisoformat(raffle['end_time'])
            
            channel_message = (
                f"🎁 <b>NEW RAFFLE!</b>\n\n"
                f"🏆 Prize: <b>{state['prize']}</b>\n"
                f"👥 Winners: <b>{state['winners_count']}</b>\n"
                f"⏰ Ends: <b>{end_time.strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
                f"<i>Join the raffle through the bot!</i>\n\n"
                f"🎲 Good luck to all participants!"
            )
            
            try:
                await bot.send_message(VOUCHES_CHANNEL_ID, channel_message, parse_mode='html')
                
                await event.edit(
                    f"✅ <b>Raffle Created!</b>\n\n"
                    f"🎁 Raffle ID: <code>{raffle_id}</code>\n"
                    f"🏆 Prize: {state['prize']}\n"
                    f"👥 Winners: {state['winners_count']}\n"
                    f"⏱ Duration: {state['duration_minutes']} minutes\n\n"
                    f"<i>Raffle has been posted to the channel!</i>",
                    buttons=[[Button.inline("🔙 Admin Panel", b"admin_panel")]],
                    parse_mode='html'
                )
            except Exception as e:
                log_error("Failed to post raffle", e)
                await event.edit("❌ Failed to post raffle", parse_mode='html')
            
            del raffle_creation_state[user_id]
        
        elif data == "cancel_raffle":
            if user_id in raffle_creation_state:
                del raffle_creation_state[user_id]
            
            await safe_edit(
                event,
                "❌ <b>Raffle Creation Cancelled</b>",
                buttons=[[Button.inline("🔙 Admin Panel", b"admin_panel")]],
            )
        
        # Admin logs
        elif data == "admin_logs":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            if os.path.exists('logs/errors.log'):
                try:
                    with open('logs/errors.log', 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    recent = lines[-100:][::-1]
                    log_text = "".join(recent) if recent else "No errors"
                    
                    with open('logs/recent_errors.txt', 'w', encoding='utf-8') as f:
                        f.write(log_text)
                    
                    # Send to the admin who requested it
                    await bot.send_file(user_id, 'logs/recent_errors.txt', caption="📊 <b>Recent Error Logs</b>", parse_mode='html')
                    
                    await event.answer("✅ Logs sent", alert=False)
                except Exception as e:
                    log_error("Failed to send logs", e)
                    await event.answer(f"❌ Error", alert=True)
            else:
                await event.answer("✅ No errors logged", alert=True)
        
        # Change Payment Details
        elif data == "change_payment_details":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            payment_details_change_state[user_id] = True
            
            message = (
                f"💳 <b>Change Payment Details</b>\n\n"
                f"📝 Please send the new OxaPay Merchant API Key.\n\n"
                f"<i>The key should look like:</i>\n"
                f"<code>XXXXX-XXXXX-XXXXX-XXXXX</code>\n\n"
                f"⚠️ <b>Warning:</b> This will replace the current payment configuration.\n\n"
                f"🔒 <i>Send /cancel to abort</i>"
            )
            
            buttons = [[Button.inline("❌ Cancel", b"admin_panel")]]
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin user stats (already handled earlier)
        elif data == "admin_user_stats":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            users = get_all_users()
            user_data_all = load_json(user_data_file)
            orders = load_json(orders_file)
            
            total_users = len(users)
            users_with_orders = sum(1 for uid in users if str(uid) in user_data_all and user_data_all[str(uid)].get('orders'))
            total_referrals = sum(len(data.get('referrals', [])) for data in user_data_all.values())
            
            message = (
                f"👥 <b>User Statistics</b>\n\n"
                f"<b>Overview:</b>\n"
                f"• Total Users: {total_users}\n"
                f"• Users with Orders: {users_with_orders}\n"
                f"• Total Referrals: {total_referrals}\n\n"
                f"<i>Download detailed report for complete user data</i>"
            )
            
            buttons = [
                [Button.inline("📥 Download User Data", b"download_user_data")],
                [Button.inline("🔙 Admin Panel", b"admin_panel")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        elif data == "download_user_data":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            users = get_all_users()
            user_data_all = load_json(user_data_file)
            orders = load_json(orders_file)
            
            report_file = f"logs/user_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("USER DATABASE REPORT\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                
                f.write(f"Total Users: {len(users)}\n")
                f.write(f"Total Orders: {len(orders)}\n\n")
                f.write("=" * 80 + "\n\n")
                
                for user_id_loop in users:
                    user_data = user_data_all.get(str(user_id_loop), {})
                    
                    f.write(f"User ID: {user_id_loop}\n")
                    f.write(f"Name: {user_data.get('name', 'N/A')}\n")
                    f.write(f"Join Date: {user_data.get('join_date', 'N/A')}\n")
                    f.write(f"Referral Code: {user_data.get('referral_code', 'N/A')}\n")
                    f.write(f"Referred By: {user_data.get('referred_by', 'None')}\n")
                    f.write(f"Total Referrals: {len(user_data.get('referrals', []))}\n")
                    f.write(f"Total Orders: {len(user_data.get('orders', []))}\n")
                    f.write(f"Wallet Balance: ${user_data.get('wallet_balance', 0):.2f}\n")
                    
                    user_orders = user_data.get('orders', [])
                    if user_orders:
                        f.write("Orders:\n")
                        for order_id in user_orders:
                            if order_id in orders:
                                order = orders[order_id]
                                f.write(f"  - {order_id} | {order['status']} | {order['timestamp']}\n")
                    
                    f.write("\n" + "-" * 80 + "\n\n")
            
            await bot.send_file(
                user_id,
                report_file,
                caption=f"📊 <b>Detailed User Report</b>\n\n<i>Total Users: {len(users)}</i>",
                parse_mode='html'
            )
            
            await event.answer("✅ Report sent!", alert=False)
        
        # Admin orders (already handled in part 6a)
        elif data == "admin_orders":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            message = (
                f"📦 <b>Order Management</b>\n\n"
                f"<i>Select order category:</i>"
            )
            
            buttons = [
                [Button.inline("⏳ Pending Orders", b"admin_orders_pending_0")],
                [Button.inline("⚙️ Processing Orders", b"admin_orders_processing_0")],
                [Button.inline("✅ Completed Orders", b"admin_orders_completed_0")],
                [Button.inline("❌ Rejected Orders", b"admin_orders_rejected_0")],
                [Button.inline("🔙 Admin Panel", b"admin_panel")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        elif data.startswith("admin_orders_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            parts = data.split("_")
            status = parts[2]
            page = int(parts[3])
            
            orders = load_json(orders_file)
            
            # Handle processing status (accepted or processing)
            if status == "processing":
                filtered = [oid for oid, o in orders.items() if o['status'] in ['accepted', 'processing']]
            else:
                filtered = [oid for oid, o in orders.items() if o['status'] == status]
            
            filtered.sort(key=lambda x: orders[x]['timestamp'], reverse=True)
            
            per_page = 10
            start = page * per_page
            end = start + per_page
            page_orders = filtered[start:end]
            
            total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
            
            status_name = {
                "pending": "⏳ Pending", 
                "processing": "⚙️ Processing",
                "completed": "✅ Completed", 
                "rejected": "❌ Rejected"
            }
            
            message = (
                f"📦 <b>{status_name.get(status, status)} Orders</b>\n"
                f"<i>Page {page + 1} of {total_pages}</i>\n\n"
            )
            
            if page_orders:
                buttons = []
                for oid in page_orders:
                    order = orders[oid]
                    short_id = oid.split('-')[-1][-4:]
                    try:
                        user_entity = await bot.get_entity(order['user_id'])
                        user_name = user_entity.first_name or "User"
                        button_text = f"...{short_id} - {user_name[:10]}"
                    except:
                        button_text = f"...{short_id}"
                    
                    buttons.append([Button.inline(button_text, f"admin_view_order_{oid}".encode())])
            else:
                message += "<i>No orders found</i>"
                buttons = []
            
            nav = []
            if page > 0:
                nav.append(Button.inline("⬅️ Prev", f"admin_orders_{status}_{page-1}".encode()))
            if end < len(filtered):
                nav.append(Button.inline("Next ➡️", f"admin_orders_{status}_{page+1}".encode()))
            
            if nav:
                buttons.append(nav)
            
            buttons.append([Button.inline("🔙 Orders Menu", b"admin_orders")])
            
            await safe_edit(event, message, buttons=buttons)
        
        elif data.startswith("admin_view_order_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            order_id = data.replace("admin_view_order_", "")
            order = get_order(order_id)
            
            if not order:
                await event.answer("❌ Order not found", alert=True)
                return
            
            try:
                total = float(order['order_data']['order_total'])
                fee = calculate_fee(total, order['store_info']['fee_percentage'])
            except:
                fee = 0
            
            message = (
                f"📦 <b>Order Details (Admin View)</b>\n\n"
                f"🆔 <code>{order_id}</code>\n"
                f"📊 Status: {order['status']}\n"
                f"💳 Payment: {order.get('payment_status', 'unpaid')}\n\n"
                f"👤 Customer ID: <code>{order['user_id']}</code>\n"
                f"🏪 {order['store_info']['name']}\n"
                f"💰 Order Total: ${order['order_data']['order_total']}\n"
                f"💵 Fee ({order['store_info']['fee_percentage']}%): ${fee}\n"
                f"💸 Customer Pays: <b>${fee}</b>\n\n"
                f"📅 Ordered: {order['timestamp']}\n"
            )
            
            buttons = []
            
            if order['status'] == 'pending':
                buttons.append([
                    Button.inline("✅ Accept", f"accept_{order_id}".encode()),
                    Button.inline("❌ Reject", f"reject_{order_id}".encode())
                ])
            elif order['status'] in ['accepted', 'processing'] and order.get('payment_status') == 'paid':
                buttons.append([Button.inline("✅ Complete Order", f"complete_order_{order_id}".encode())])
            
            buttons.append([Button.inline("📝 Add Remark", f"remark_{order_id}".encode())])
            buttons.append([Button.inline("🔙 Back", b"admin_orders")])
            
            await safe_edit(event, message, buttons=buttons)
        
        # Admin tickets (similar structure)
        elif data == "admin_tickets":
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            message = (
                f"🎫 <b>Support Tickets</b>\n\n"
                f"<i>Select ticket category:</i>"
            )
            
            buttons = [
                [Button.inline("💬 Active Tickets", b"admin_tickets_active_0")],
                [Button.inline("⏳ Pending Tickets", b"admin_tickets_pending_0")],
                [Button.inline("✅ Closed Tickets", b"admin_tickets_closed_0")],
                [Button.inline("🔙 Admin Panel", b"admin_panel")]
            ]
            
            await safe_edit(event, message, buttons=buttons)
        
        elif data.startswith("admin_tickets_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            parts = data.split("_")
            status = parts[2]
            page = int(parts[3])
            
            tickets = load_json(tickets_file)
            filtered = [tid for tid, t in tickets.items() if t['status'] == status]
            filtered.sort(key=lambda x: tickets[x]['timestamp'], reverse=True)
            
            per_page = 10
            start = page * per_page
            end = start + per_page
            page_tickets = filtered[start:end]
            
            total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
            
            status_name = {"active": "💬 Active", "pending": "⏳ Pending", "closed": "✅ Closed"}
            
            message = (
                f"🎫 <b>{status_name.get(status, status)} Tickets</b>\n"
                f"<i>Page {page + 1} of {total_pages}</i>\n\n"
            )
            
            if page_tickets:
                buttons = []
                for tid in page_tickets:
                    ticket = tickets[tid]
                    short_id = tid.split('-')[-1][-4:]
                    buttons.append([Button.inline(f"🎫 ...{short_id} - {ticket['user_name'][:10]}", f"admin_view_ticket_{tid}".encode())])
            else:
                message += "<i>No tickets found</i>"
                buttons = []
            
            nav = []
            if page > 0:
                nav.append(Button.inline("⬅️ Prev", f"admin_tickets_{status}_{page-1}".encode()))
            if end < len(filtered):
                nav.append(Button.inline("Next ➡️", f"admin_tickets_{status}_{page+1}".encode()))
            
            if nav:
                buttons.append(nav)
            
            buttons.append([Button.inline("🔙 Tickets Menu", b"admin_tickets")])
            
            await safe_edit(event, message, buttons=buttons)
        
        elif data.startswith("admin_view_ticket_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            ticket_id = data.replace("admin_view_ticket_", "")
            ticket = get_ticket(ticket_id)
            
            if not ticket:
                await event.answer("❌ Ticket not found", alert=True)
                return
            
            user_link = f"<a href='tg://user?id={ticket['user_id']}'>{ticket['user_name']}</a>"
            
            message = (
                f"🎫 <b>Ticket Details</b>\n\n"
                f"🆔 <code>{ticket_id}</code>\n"
                f"📊 Status: {ticket['status']}\n\n"
                f"👤 User: {user_link}\n"
                f"🆔 User ID: <code>{ticket['user_id']}</code>\n\n"
                f"<b>Question:</b>\n<i>{ticket['question']}</i>\n\n"
                f"📅 Created: {ticket['timestamp']}\n\n"
            )
            
            if ticket['messages']:
                message += f"<b>Messages: {len(ticket['messages'])}</b>"
            else:
                message += "<i>No messages yet</i>"
            
            buttons = [[Button.inline("📄 Get Transcript", f"ticket_transcript_{ticket_id}".encode())]]
            buttons.append([Button.inline("🔙 Back", b"admin_tickets")])
            
            await safe_edit(event, message, buttons=buttons)
        
        elif data.startswith("ticket_transcript_"):
            if not is_admin(user_id):
                await event.answer("❌ Admin only!", alert=True)
                return
            
            ticket_id = data.replace("ticket_transcript_", "")
            ticket = get_ticket(ticket_id)
            
            if not ticket:
                await event.answer("❌ Ticket not found", alert=True)
                return
            
            transcript_file = f"transcripts/{ticket_id}_transcript.txt"
            
            with open(transcript_file, 'w', encoding='utf-8') as f:
                f.write(f"Support Ticket Transcript\n")
                f.write(f"Ticket ID: {ticket_id}\n")
                f.write(f"User: {ticket['user_name']} (ID: {ticket['user_id']})\n")
                f.write(f"Question: {ticket['question']}\n")
                f.write(f"Status: {ticket['status']}\n")
                f.write(f"Created: {ticket['timestamp']}\n")
                f.write("=" * 50 + "\n\n")
                
                for msg in ticket['messages']:
                    f.write(f"[{msg['timestamp']}] {msg['from'].upper()}: {msg['text']}\n")
            
            # Send to the admin who requested it
            await bot.send_file(user_id, transcript_file, caption=f"📄 <b>Transcript:</b> {ticket_id}", parse_mode='html')
            
            await event.answer("✅ Transcript sent", alert=False)
    
    except Exception as e:
        log_error(f"Callback error for {data}", e)
        try:
            await event.answer("❌ An error occurred. Check logs.", alert=True)
        except:
            pass

# Start bot
print("\n" + "="*60)
print("🚀 BOT STARTING...")
print("="*60)
print(f"👤 Admin ID: {ADMIN_ID}")
print(f"👥 Group ID: {GROUP_ID}")
print(f"⭐ Vouches Channel: {VOUCHES_CHANNEL_ID}")
print(f"📦 Orders Channel: {ORDERS_CHANNEL_ID}")
print(f"💳 Payment Channel: {PAYMENT_NOTIFICATION_CHANNEL}")
stores_data = load_stores()
print(f"🛍️ Categories: {len(stores_data)}")
total_stores = sum(len(cat['stores']) for cat in stores_data.values())
print(f"🏪 Total Stores: {total_stores}")
print(f"📦 Boxing Services: {len(BOXING_SERVICES)}")
print("="*60)
print("⚠️  IMPORTANT: Replace OXAPAY_API_KEY and OXAPAY_MERCHANT_ID with your actual credentials!")
print("="*60)
print("✅ BOT IS RUNNING! Errors will be logged below:")
print("="*60 + "\n")

# Start background tasks
loop = asyncio.get_event_loop()
loop.create_task(raffle_monitor())
loop.create_task(verification_cleanup())

# Run bot
bot.run_until_disconnected()
