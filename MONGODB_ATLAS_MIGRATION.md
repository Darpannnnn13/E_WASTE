# MongoDB Atlas Migration Guide

## Quick Start

### Step 1: Get Your MongoDB Atlas Connection String

1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Sign in or create account
3. Create a free cluster
4. Click "Connect" on your cluster
5. Choose "Connect your application"
6. Copy the connection string (it will look like):
   ```
   mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/ewaste_db?retryWrites=true&w=majority
   ```

### Step 2: Add to .env File

Add this line to your `.env` file in the project root:

```
MONGO_ATLAS_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/ewaste_db?retryWrites=true&w=majority
```

Replace:
- `username` - Your MongoDB Atlas username
- `password` - Your MongoDB Atlas password  
- `cluster0.xxxxx` - Your cluster name

### Step 3: Run Migration

Make sure your local MongoDB is running, then run:

```bash
python seed_to_atlas.py
```

The script will:
- ✓ Connect to your local MongoDB
- ✓ Export all data from all collections
- ✓ Import data into MongoDB Atlas
- ✓ Create necessary indexes
- ✓ Verify the migration was successful

## Expected Output

```
============================================================
MongoDB Migration: Local → Atlas
============================================================
✓ Configuration validated
  Local MongoDB: mongodb://localhost:27017/
  Atlas MongoDB: mongodb+srv://username:password@cluster0...

Connecting to local MongoDB...
✓ Connected to local MongoDB
  Database: ewaste_db

Connecting to MongoDB Atlas...
✓ Connected to MongoDB Atlas
  Database: ewaste_db

============================================================
MIGRATION IN PROGRESS
============================================================

Found 10 collection(s) to migrate:

  → users: Fetching 8 documents... Inserting... ✓ 8 docs
  → pickup_requests: Fetching 50 documents... Inserting... ✓ 50 docs
  → collection_clusters: Fetching 10 documents... Inserting... ✓ 10 docs
  → category_prices: Fetching 15 documents... Inserting... ✓ 15 docs
  → metal_prices: Fetching 1 documents... Inserting... ✓ 1 doc
  ...

============================================================
MIGRATION SUMMARY
============================================================
✓ Total Documents Migrated: 150+
✓ Collections Migrated: 10/10

============================================================
VERIFICATION
============================================================

Collection Comparison:
  ✓ users: 8 docs (matched)
  ✓ pickup_requests: 50 docs (matched)
  ...

============================================================
CREATING INDEXES
============================================================

  ✓ users.email (unique)
  ✓ pickup_requests.user_id
  ✓ collection_clusters.engineer_id
  ...

✓ MIGRATION COMPLETED SUCCESSFULLY
============================================================

✓ Your data is now available on MongoDB Atlas!
✓ Timestamp: 2026-01-11 10:30:45
```

## What Gets Migrated

The script migrates ALL collections from your local MongoDB:

- `users` - All user accounts (drivers, engineers, warehouse, recyclers, etc.)
- `pickup_requests` - All pickup requests with coordinates and details
- `collection_clusters` - All assigned pickup clusters
- `category_prices` - Pricing information
- `metal_prices` - Metal pricing data
- `notifications` - User notifications
- `active_routes` - Real-time driver routes
- `driver_locations` - Driver GPS locations
- Any other custom collections

## Troubleshooting

### Connection Refused Error
```
❌ Failed to connect to local MongoDB: ...
Make sure MongoDB is running on localhost:27017
```
**Solution:** Start your local MongoDB:
```bash
mongod
```

### Atlas Connection Error
```
❌ Failed to connect to MongoDB Atlas: ...
Check your MONGO_ATLAS_URI in .env
```
**Solution:** 
- Verify your connection string in `.env`
- Check that your IP is whitelisted in MongoDB Atlas (Security → Network Access)
- Ensure your username/password are correct

### MONGO_ATLAS_URI Not Found
```
❌ ERROR: MONGO_ATLAS_URI not found in environment variables
```
**Solution:** Add `MONGO_ATLAS_URI` to your `.env` file

## After Migration

### Update Your Application to Use Atlas

Change your `.env` file to use Atlas:

```
# Use this for development with Atlas
MONGO_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/ewaste_db?retryWrites=true&w=majority
```

OR keep both connections:

```
# Local MongoDB (optional, for local testing)
MONGO_URI=mongodb://localhost:27017/ewaste_db

# MongoDB Atlas (for production)
MONGO_ATLAS_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/ewaste_db?retryWrites=true&w=majority
```

### Backup Your Local Data

Before switching to Atlas, backup your local MongoDB:

```bash
mongodump --db ewaste_db --out ./backup
```

## Advanced Options

### Re-run Migration (Clear Existing Data)

The script automatically clears collections before importing. Just run again:

```bash
python seed_to_atlas.py
```

### Migrate Only Specific Collections

Edit the script to filter collections:

```python
# In migrate_data() function, modify:
collections = get_all_collections(local_db)
collections = [c for c in collections if c in ['users', 'pickup_requests']]  # Only these
```

### Scheduled Sync (Optional)

Create a scheduled task to sync data periodically:

```bash
# On Windows (Task Scheduler)
# On Mac/Linux (Crontab)
0 2 * * * cd /path/to/E_WASTE && python seed_to_atlas.py
```

## Security Notes

- Never commit your `.env` file with credentials to git
- Use strong passwords for MongoDB Atlas
- Rotate credentials regularly
- Use IP whitelisting in MongoDB Atlas for production
- Consider using MongoDB Realm for app-specific credentials

## Support

If you encounter issues:

1. Check MongoDB Atlas status: https://status.mongodb.com/
2. Verify network connectivity
3. Check MongoDB logs: `tail -f /var/log/mongodb/mongod.log` (Linux/Mac)
4. Run with verbose logging (modify script to add `pymongo.diagnostics()`)
