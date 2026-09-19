"""Plot every admitted candidate; failed and unexecuted are not numeric losses."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def load_panel(path):
    raw = path.read_bytes()
    data = json.loads(raw)
    rows = data['rows']
    tasks = {r['task'] for r in rows}
    if len(tasks) != 1 or len(rows) != 18:
        raise ValueError('one task and the originally scheduled eighteen rows required')
    for seed in (1, 2, 3):
        group = [r for r in rows if r['seed'] == seed]
        if len(group) != 6 or len({r['slot'] for r in group}) != 6:
            raise ValueError('complete candidate identities required')
        if sum(r['original_selected'] is True for r in group) != 2:
            raise ValueError('originally selected pair required')
        for row in group:
            if row['valid'] is not None and type(row['valid']) is not bool:
                raise ValueError('validity must be boolean or unknown')
            if row['valid'] is True and (type(row['score']) not in (float, int)
                                        or not math.isfinite(row['score']) or row['score'] < 0):
                raise ValueError('finite nonnegative loss required')
    return dict(task=next(iter(tasks)), rows=rows,
                summary_sha256=hashlib.sha256(raw).hexdigest())


def render(paths, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    panels = [load_panel(path) for path in paths]
    if output.exists() or output.with_suffix('.receipt.json').exists():
        raise FileExistsError('do not replace an earlier rendered artifact')
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, len(panels), squeeze=False, figsize=(6.1 * len(panels), 5.9),
                             gridspec_kw={'height_ratios': [4, 1.25]}, sharex='col')
    colors = {True: '#b65316', False: '#697a8a'}
    titles = {'leaf-classification': 'Leaf', 'spooky-author-identification': 'Spooky'}
    for col, panel in enumerate(panels):
        top, bottom = axes[:, col]
        for row in sorted(panel['rows'], key=lambda r: (r['seed'], r['slot'])):
            x = row['seed'] + (row['slot'] - 2.5) * .105
            color = colors[row['original_selected']]
            if row['valid'] is True:
                top.scatter(x, row['score'], color=color, s=65, zorder=3,
                            edgecolor='white', linewidth=.7)
            else:
                bottom.scatter(x, 1 if row['valid'] is False else 0, color=color,
                               marker='x' if row['valid'] is False else '|', s=55)
        top.set_title(titles.get(panel['task'], panel['task']), loc='left', fontweight='bold')
        top.set_ylabel('Official log loss (lower is better)')
        top.set_ylim(bottom=0)
        top.grid(axis='y', alpha=.22)
        top.tick_params(axis='x', bottom=False, labelbottom=False)
        bottom.set_yticks([0, 1], ['Unknown / unstarted', 'No valid output'], fontsize=9)
        bottom.set_ylim(-.65, 1.65)
        bottom.set_xticks([1, 2, 3], ['Seed 1', 'Seed 2', 'Seed 3'])
        bottom.set_xlim(.5, 3.5)
        for ax in (top, bottom):
            ax.spines[['top', 'right']].set_visible(False)
        for seed in (1, 2, 3):
            group = [r for r in panel['rows'] if r['seed'] == seed]
            valid = sum(r['valid'] is True for r in group)
            unknown = sum(r['valid'] is None for r in group)
            label = f'{valid}/6 valid' if not unknown else f'{unknown}/6 unknown'
            top.text(seed, .97, label, transform=top.get_xaxis_transform(),
                     ha='center', va='top', fontsize=9)
    fig.suptitle('Complete initial candidate pools\nAll originally scheduled programs',
                 fontsize=13, fontweight='bold', y=1.025)
    fig.legend(handles=[Line2D([], [], marker='o', linestyle='', color=colors[b],
                              label=label) for b, label in
                        [(True, 'Originally selected (2 per pool)'), (False, 'Originally unselected (4 per pool)')]],
               loc='upper center', bbox_to_anchor=(.5, .935), ncol=min(2, len(panels)), frameon=False,
               fontsize=9)
    fig.text(.5, .025, 'Same fresh environment within each pool; original programs unchanged.\n'
             'Exploratory diagnostic, not deployed final selection or E2E gain.',
             ha='center', fontsize=8.5)
    fig.subplots_adjust(top=.82, bottom=.16, hspace=.12, wspace=.36, left=.1, right=.97)
    fig.savefig(output, dpi=170, bbox_inches='tight', pad_inches=.16)
    plt.close(fig)
    receipt = dict(role='descriptive_plot_no_new_endpoint', output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                   panels=[{k: v for k, v in p.items() if k != 'rows'} for p in panels])
    with output.with_suffix('.receipt.json').open('x') as handle:
        json.dump(receipt, handle, indent=2)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('summaries', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    render(args.summaries, args.output)
