import datetime
import sys
import os
from peewee import *
from tabulate import tabulate
import matplotlib.pyplot as plt

# Import project models
from database.db_operations import (
    ClusterUptime,
    ClusterCumulativeUptime,
    ClusterInfo,
    initialize_production_db
)

def get_report_data(days=30):
    start_date = datetime.date.today() - datetime.timedelta(days=days)
    
    # Query daily records
    query = (
             ClusterCumulativeUptime
             .select(ClusterCumulativeUptime.date, 
                     ClusterCumulativeUptime.daily_use_seconds, 
                     ClusterInfo.cluster_name)
             .join(ClusterInfo, on=(ClusterCumulativeUptime.cluster == ClusterInfo.cluster_id))
             .where(ClusterCumulativeUptime.date >= start_date)
             .order_by(ClusterCumulativeUptime.date.asc()))
    
    data = {}
    clusters = set()
    dates = set()
    
    for row in query:
        date_str = row.date.strftime('%Y-%m-%d')
        cluster_name = row.clusterinfo.cluster_name
        seconds = row.daily_use_seconds
        
        if date_str not in data:
            data[date_str] = {}
        data[date_str][cluster_name] = seconds
        clusters.add(cluster_name)
        dates.add(date_str)
        
    sorted_dates = sorted(list(dates))
    sorted_clusters = sorted(list(clusters))
    
    return sorted_dates, sorted_clusters, data

def print_text_report(dates, clusters, data):
    print("\nCluster Usage Report (seconds per day)\n")
    headers = ["Date"] + clusters
    table = []
    for d in dates:
        row = [d]
        for c in clusters:
            row.append(int(data[d].get(c, 0)))
        table.append(row)
    
    print(tabulate(table, headers=headers, tablefmt="grid"))

def generate_graph(dates, clusters, data, output_file="cluster_usage.png"):
    # 1. Process data: Top 5 per day + Other, and convert to hours
    processed_data = {d: {} for d in dates}
    important_clusters = set()
    
    for d in dates:
        day_usage = data[d]
        # Sort by usage descending
        sorted_usage = sorted(day_usage.items(), key=lambda x: x[1], reverse=True)
        
        top_5 = sorted_usage[:5]
        others = sorted_usage[5:]
        
        for c_name, val in top_5:
            processed_data[d][c_name] = val / 3600.0
            important_clusters.add(c_name)
        
        if others:
            other_val = sum(v for k, v in others)
            processed_data[d]['Other'] = other_val / 3600.0
        else:
            processed_data[d]['Other'] = 0.0

    # Consistent legend order: Important clusters alphabetically, then 'Other'
    if 'Other' in important_clusters:
        important_clusters.remove('Other')
    all_series = sorted(list(important_clusters)) + ['Other']

    # Prepare data for plotting
    plot_data = {c: [] for c in all_series}
    for d in dates:
        for c in all_series:
            plot_data[c].append(processed_data[d].get(c, 0))

    fig, ax = plt.subplots(figsize=(12, 6))
    bottom = [0.0] * len(dates)

    for c in all_series:
        # Only plot if there's any data for this series across all dates
        if any(plot_data[c]):
            ax.bar(dates, plot_data[c], label=c, bottom=bottom)
            bottom = [b + v for b, v in zip(bottom, plot_data[c])]

    ax.set_ylabel('Hours')
    ax.set_title('Cluster Daily Usage (Top 5 + Other)')
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize='small')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    plt.savefig(output_file)
    print(f"\nGraph saved to {output_file}")

def main():
    # Fix database path for this environment
    import database.db_operations as db_ops
    db_ops.DATABASE_FILE_NAME = os.path.abspath('../cluster_uptimes.db')
    
    # Initialize DB
    db = initialize_production_db()
    
    days = 30
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            pass
        
    dates, clusters, data = get_report_data(days)
    
    if not dates:
        print("No data found for the specified period.")
        return

    print_text_report(dates, clusters, data)
    generate_graph(dates, clusters, data)

if __name__ == "__main__":
    # gemini 2025-01-25 15:35
    main()
