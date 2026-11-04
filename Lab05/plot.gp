set terminal pngcairo size 1100,600
set output datadir.'/tcp.png'
set xlabel 'Time (s)'
set ylabel 'Throughput (Mbit/s)'
set title 'TCP: 30-second observation in isolated VM network'
set grid
plot datadir.'/tcp.tsv' using 1:2 with linespoints title 'iperf 2'
