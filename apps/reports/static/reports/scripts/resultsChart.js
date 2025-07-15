document.addEventListener("DOMContentLoaded", function () {
    const chartData = JSON.parse(document.getElementById('chart-data').textContent);
    
    const ctx = document.getElementById('resultsChart').getContext('2d');

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Peak Score (%)',
                data: chartData.data,
                backgroundColor: 'rgba(54, 162, 235, 0.6)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'x',
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        stepSize: 10
                    },
                    title: {
                        display: true,
                        text: 'Score (%)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Peaks'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
});