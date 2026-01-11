"""
Migration Script: Export Local MongoDB → MongoDB Atlas

This script exports ALL data from your local MongoDB instance
and imports it into MongoDB Atlas.

Usage:
  python seed_to_atlas.py

Requirements:
  - Local MongoDB running on localhost:27017
  - MongoDB Atlas connection string in .env as MONGO_ATLAS_URI
  
Environment Variables:
  - MONGO_URI: Local MongoDB URI (default: mongodb://localhost:27017/ewaste_db)
  - MONGO_ATLAS_URI: MongoDB Atlas connection string (REQUIRED)
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import sys
from datetime import datetime

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# ========== CONFIGURATION ==========
LOCAL_MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
# Hardcoded Atlas URI - REPLACE 'YOUR_CLUSTER_DOMAIN' with your actual cluster address
# ATLAS_MONGO_URI = "mongodb+srv://darpanmeher1346_db_user:4ADuKCFNWjFbvwue@YOUR_CLUSTER_DOMAIN/ewaste_db?retryWrites=true&w=majority"
ATLAS_MONGO_URI = "mongodb+srv://sahilashar21:LOBqKPV3GcmxNEsJ@cluster0.qbnh7lv.mongodb.net/library?retryWrites=true&w=majority&appName=Cluster0"
# mongoose.connect("mongodb+srv://sahilashar21:LOBqKPV3GcmxNEsJ@cluster0.qbnh7lv.mongodb.net/library?retryWrites=true&w=majority&appName=Cluster0")
DATABASE_NAME = 'ewaste_db'

# ========== VALIDATION ==========
def validate_configuration():
    """Validate that required configurations are present"""
    print("=" * 60)
    print("MongoDB Migration: Local → Atlas")
    print("=" * 60)
    
    if not ATLAS_MONGO_URI:
        print("❌ ERROR: ATLAS_MONGO_URI is not defined in the script.")
        sys.exit(1)
    
    if "YOUR_CLUSTER_DOMAIN" in ATLAS_MONGO_URI.upper():
        print("❌ ERROR: ATLAS_MONGO_URI contains placeholder 'YOUR_CLUSTER_DOMAIN'")
        print("  Please open seed_to_atlas.py and replace 'YOUR_CLUSTER_DOMAIN' with your actual Cluster URL.")
        sys.exit(1)
    
    print("✓ Configuration validated")
    print(f"  Local MongoDB: {LOCAL_MONGO_URI}")
    print(f"  Atlas MongoDB: {ATLAS_MONGO_URI[:50]}...")
    print()


# ========== CONNECTION ==========
def connect_local_db():
    """Connect to local MongoDB"""
    try:
        print("Connecting to local MongoDB...")
        client = MongoClient(LOCAL_MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        
        try:
            db = client.get_default_database()
            if db is None:
                db = client[DATABASE_NAME]
        except Exception:
            db = client[DATABASE_NAME]
        
        print(f"✓ Connected to local MongoDB")
        print(f"  Database: {db.name}")
        return client, db
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"❌ Failed to connect to local MongoDB: {e}")
        print("  Make sure MongoDB is running on localhost:27017")
        sys.exit(1)


def connect_atlas_db():
    """Connect to MongoDB Atlas"""
    try:
        print("Connecting to MongoDB Atlas...")
        client = MongoClient(ATLAS_MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        
        # Get database name from URI
        db_name = DATABASE_NAME
        if '/' in ATLAS_MONGO_URI:
            parts = ATLAS_MONGO_URI.split('/')
            if len(parts) > 3:
                db_name = parts[-1].split('?')[0]
        
        db = client[db_name]
        
        print(f"✓ Connected to MongoDB Atlas")
        print(f"  Database: {db.name}")
        return client, db
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"❌ Failed to connect to MongoDB Atlas: {e}")
        print("  Check your MONGO_ATLAS_URI in .env")
        sys.exit(1)


# ========== MIGRATION ==========
def get_all_collections(db):
    """Get all collection names"""
    system_collections = {'system.indexes', 'system.profile', 'system.views'}
    collections = [c for c in db.list_collection_names() if c not in system_collections]
    return collections


def get_collection_size(collection):
    """Get total document count in collection"""
    return collection.count_documents({})


def copy_collection(source_col, target_col, col_name):
    """Copy all documents from source to target collection"""
    try:
        doc_count = get_collection_size(source_col)
        
        if doc_count == 0:
            print(f"  ⊘ {col_name}: 0 documents (skipped)")
            return 0
        
        print(f"  → {col_name}: Fetching {doc_count} documents...", end='', flush=True)
        
        # Fetch all documents
        documents = list(source_col.find({}))
        
        print(f" Inserting...", end='', flush=True)
        
        # Delete existing documents in target (clean slate)
        target_col.delete_many({})
        
        # Insert all documents
        if documents:
            result = target_col.insert_many(documents)
            print(f" ✓ {len(result.inserted_ids)} docs")
            return len(result.inserted_ids)
        
        return 0
    except Exception as e:
        print(f"\n  ❌ Error copying {col_name}: {e}")
        return 0


def migrate_data(local_db, atlas_db):
    """Migrate all data from local to Atlas"""
    print("\n" + "=" * 60)
    print("MIGRATION IN PROGRESS")
    print("=" * 60 + "\n")
    
    collections = get_all_collections(local_db)
    
    if not collections:
        print("❌ No collections found in local database")
        return False
    
    print(f"Found {len(collections)} collection(s) to migrate:\n")
    
    total_docs = 0
    successful = 0
    failed = 0
    
    for col_name in sorted(collections):
        try:
            source_col = local_db[col_name]
            target_col = atlas_db[col_name]
            
            docs_copied = copy_collection(source_col, target_col, col_name)
            total_docs += docs_copied
            
            if docs_copied > 0:
                successful += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ {col_name}: {e}")
            failed += 1
    
    # Migration summary
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    print(f"✓ Total Documents Migrated: {total_docs}")
    print(f"✓ Collections Migrated: {successful}/{len(collections)}")
    
    if failed > 0:
        print(f"⚠ Collections Failed: {failed}")
    
    return True


def verify_migration(local_db, atlas_db):
    """Verify that data was migrated correctly"""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60 + "\n")
    
    local_collections = set(get_all_collections(local_db))
    atlas_collections = set(get_all_collections(atlas_db))
    
    print("Collection Comparison:")
    for col_name in sorted(local_collections):
        local_count = local_db[col_name].count_documents({})
        atlas_count = atlas_db[col_name].count_documents({})
        
        if local_count == atlas_count:
            print(f"  ✓ {col_name}: {local_count} docs (matched)")
        else:
            print(f"  ⚠ {col_name}: Local={local_count}, Atlas={atlas_count}")
    
    # Check for collections in Atlas but not in Local
    extra_in_atlas = atlas_collections - local_collections
    if extra_in_atlas:
        print(f"\n⚠ Extra collections in Atlas: {', '.join(sorted(extra_in_atlas))}")


def create_indexes(db):
    """Create recommended indexes on Atlas database"""
    print("\n" + "=" * 60)
    print("CREATING INDEXES")
    print("=" * 60 + "\n")
    
    try:
        # Index on users
        db.users.create_index([('email', 1)], unique=True, sparse=True)
        print("  ✓ users.email (unique)")
        
        # Indexes on pickup_requests
        db.pickup_requests.create_index([('user_id', 1)])
        print("  ✓ pickup_requests.user_id")
        
        db.pickup_requests.create_index([('status', 1)])
        print("  ✓ pickup_requests.status")
        
        # Indexes on collection_clusters
        db.collection_clusters.create_index([('engineer_id', 1)])
        print("  ✓ collection_clusters.engineer_id")
        
        db.collection_clusters.create_index([('driver_id', 1)])
        print("  ✓ collection_clusters.driver_id")
        
        db.collection_clusters.create_index([('status', 1)])
        print("  ✓ collection_clusters.status")
        
        # Indexes on notifications
        if 'notifications' in db.list_collection_names():
            db.notifications.create_index([('engineer_id', 1), ('read', 1)])
            print("  ✓ notifications.engineer_id, read")
        
        # Indexes on active_routes
        if 'active_routes' in db.list_collection_names():
            db.active_routes.create_index([('driver_id', 1), ('status', 1)])
            print("  ✓ active_routes.driver_id, status")
        
        print("\n✓ Indexes created successfully")
    except Exception as e:
        print(f"\n⚠ Error creating indexes: {e}")


# ========== MAIN ==========
def main():
    """Main migration process"""
    try:
        # Validate configuration
        validate_configuration()
        
        # Connect to databases
        local_client, local_db = connect_local_db()
        atlas_client, atlas_db = connect_atlas_db()
        
        # Migrate data
        success = migrate_data(local_db, atlas_db)
        
        if not success:
            sys.exit(1)
        
        # Verify migration
        verify_migration(local_db, atlas_db)
        
        # Create indexes on Atlas
        create_indexes(atlas_db)
        
        # Final summary
        print("\n" + "=" * 60)
        print("✓ MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"\n✓ Your data is now available on MongoDB Atlas!")
        print(f"✓ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Close connections
        local_client.close()
        atlas_client.close()
        
    except KeyboardInterrupt:
        print("\n\n⚠ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if "DNS query name does not exist" in str(e):
            print("  💡 Hint: Check your MONGO_ATLAS_URI in .env. It seems to have an invalid domain.")
        sys.exit(1)


if __name__ == '__main__':
    main()
