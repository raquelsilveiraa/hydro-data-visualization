(() => {
    const graph = document.getElementById('{plot_id}');
    const toolbar = document.querySelector('.chart-toolbar');
    const period = document.getElementById('chart-period');
    const toTime = value => {
        const text = String(value).replace(' ', 'T');
        const iso = text.includes('T') ? text : text + 'T00:00:00';
        return Date.parse(iso.endsWith('Z') ? iso : iso + 'Z');
    };
    const observed = [toTime(graph.data[0].x[0]), toTime(graph.data[0].x[graph.data[0].x.length - 1])];
    const dateLabel = value => new Date(value).toLocaleDateString('fr-FR', {timeZone:'UTC'});
    const buttons = Object.fromEntries([...toolbar.querySelectorAll('[data-chart-action]')].map(button => [button.dataset.chartAction, button]));
    function currentRange() {
        return graph._fullLayout.xaxis.range.map(toTime);
    }
    function syncControls() {
        const range = currentRange();
        period.textContent = dateLabel(range[0]) + ' — ' + dateLabel(range[1]);
        buttons.previous.disabled = range[0] <= observed[0];
        buttons.next.disabled = range[1] >= observed[1];
        buttons.pan.setAttribute('aria-pressed', String(graph._fullLayout.dragmode === 'pan'));
        toolbar.querySelectorAll('[data-trace]').forEach(input => {
            const visible = graph.data[Number(input.dataset.trace)].visible;
            input.checked = visible !== false && visible !== 'legendonly';
        });
    }
    toolbar.querySelectorAll('[data-trace]').forEach(input => {
        input.addEventListener('change', () => {
            Plotly.restyle(graph, {visible: input.checked ? true : 'legendonly'}, [Number(input.dataset.trace)]);
        });
    });
    buttons.pan.onclick = () => Plotly.relayout(graph, {dragmode: graph._fullLayout.dragmode === 'pan' ? 'zoom' : 'pan'});
    buttons.reset.onclick = () => Plotly.relayout(graph, {
        'xaxis.autorange':true, 'xaxis2.autorange':true,
        'yaxis.autorange':true, 'yaxis2.autorange':true, 'yaxis3.autorange':true,
        dragmode:'zoom'
    });
    function shiftRange(direction) {
        const range = currentRange();
        const span = range[1] - range[0];
        if (!Number.isFinite(span) || span <= 0 || span >= observed[1] - observed[0]) return;
        const start = Math.max(observed[0], Math.min(observed[1] - span, range[0] + direction * span * 0.8));
        const next = [new Date(start).toISOString(), new Date(start + span).toISOString()];
        Plotly.relayout(graph, {'xaxis.range':next, 'xaxis2.range':next});
    }
    buttons.previous.onclick = () => shiftRange(-1);
    buttons.next.onclick = () => shiftRange(1);
    graph.on('plotly_relayout', syncControls);
    graph.on('plotly_restyle', syncControls);
    document.addEventListener('click', event => {
        const menu = toolbar.querySelector('.curve-menu');
        if (!menu.contains(event.target)) menu.open = false;
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') toolbar.querySelector('.curve-menu').open = false;
    });
    syncControls();
})();
