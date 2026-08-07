import json
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_path", type=str, required=True)
    args = parser.parse_args()

    with open(args.input_path, "r") as f:
        data = [json.loads(line) for line in f]

    tasks_stats = {}
    better_id_stats = {}
    worse_id_stats = {}
    subtree_stats = {}

    for item in data:
        task = item["task"]
        better_id = item["better"]
        worse_id = item["worse"]
        subtree_difference = item["subtree_sizes"][0] - item["subtree_sizes"][1]

        if task not in tasks_stats:
            tasks_stats[task] = 0
        tasks_stats[task] += 1

        if better_id not in better_id_stats:
            better_id_stats[better_id] = 0
        better_id_stats[better_id] += 1

        if worse_id not in worse_id_stats:
            worse_id_stats[worse_id] = 0
        worse_id_stats[worse_id] += 1

        if subtree_difference not in subtree_stats:
            subtree_stats[subtree_difference] = 0
        subtree_stats[subtree_difference] += 1

    # Sort the statistics dictionaries by the values in descending order
    tasks_stats = dict(sorted(tasks_stats.items(), key=lambda item: item[1], reverse=True))
    better_id_stats = dict(sorted(better_id_stats.items(), key=lambda item: item[1], reverse=True))
    worse_id_stats = dict(sorted(worse_id_stats.items(), key=lambda item: item[1], reverse=True))
    subtree_stats = dict(sorted(subtree_stats.items(), key=lambda item: item[1], reverse=True))

    # Take top 10 entries for each statistics dictionary
    tasks_stats = dict(list(tasks_stats.items())[:10])
    better_id_stats = dict(list(better_id_stats.items())[:10])
    worse_id_stats = dict(list(worse_id_stats.items())[:10])
    subtree_stats = dict(list(subtree_stats.items())[:10])

    print(f"Top 10 Task Statistics: {tasks_stats}")
    print("------------------------")
    print(f"Top 10 Better ID Statistics: {better_id_stats}")
    print("------------------------")
    print(f"Top 10 Worse ID Statistics: {worse_id_stats}")
    print("------------------------")
    print(f"Top 10 Subtree Size Difference Statistics: {subtree_stats}")
    print("================================")

    # Take last 10 entries for each statistics dictionary
    tasks_stats_last = dict(list(tasks_stats.items())[-10:])
    better_id_stats_last = dict(list(better_id_stats.items())[-10:])   
    worse_id_stats_last = dict(list(worse_id_stats.items())[-10:])
    subtree_stats_last = dict(list(subtree_stats.items())[-10:])

    
    print(f"Last 10 Task Statistics: {tasks_stats_last}")
    print("------------------------")
    print(f"Last 10 Better ID Statistics: {better_id_stats_last}")
    print("------------------------")
    print(f"Last 10 Worse ID Statistics: {worse_id_stats_last}")
    print("------------------------")
    print(f"Last 10 Subtree Size Difference Statistics: {subtree_stats_last}")
