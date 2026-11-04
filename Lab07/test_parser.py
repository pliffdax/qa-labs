import pytest
from parser import parser, check_thresholds, complete_intervals

def test_units_and_totals():
 text='[  5] 0.00-1.00 sec  3.00 MBytes 25.2 Mbits/sec 0 320 KBytes\n[ 5] 0.00-3.00 sec 9.00 MBytes 25.2 Mbits/sec sender'
 rows=parser(text)
 assert len(rows)==1
 assert rows[0]['TransferBytes']==3*1024**2
 assert rows[0]['Bitrate']==25_200_000
 assert rows[0]['CwndBytes']==320*1024

def test_empty_or_error_is_not_success():
 with pytest.raises(ValueError):parser('iperf3: error - unable to connect')

def test_gigabit_and_kilobyte_units():
 row=parser('[ 7] 1.00-2.00 sec 900 KBytes 1.23 Gbits/sec')[0]
 assert row['TransferBytes']==900*1024
 assert row['Bitrate']==1_230_000_000

def measurements(transfer='3.00', bitrate='25.2'):
 return parser('\n'.join(
  f'[ 5] {start:.2f}-{start+1:.2f} sec {transfer} MBytes {bitrate} Mbits/sec 0 320 KBytes'
  for start in range(3)))

def test_all_three_seconds_are_required():
 with pytest.raises(AssertionError,match='Missing measurement coverage'):
  check_thresholds(measurements()[:1])

def test_final_partial_is_allowed_but_middle_partial_is_not():
 text='\n'.join(f'[ 5] {i}.00-{i+1}.00 sec 3 MBytes 25.2 Mbits/sec' for i in range(3))
 rows=parser(text+'\n[ 5] 3.00-3.02 sec 10 KBytes 4 Mbits/sec')
 assert len(check_thresholds(rows))==3
 broken=parser('[ 5] 0.00-1.00 sec 3 MBytes 25.2 Mbits/sec\n'
  '[ 5] 1.00-1.50 sec 100 KBytes 1 Mbits/sec\n'
  '[ 5] 1.50-2.50 sec 3 MBytes 25.2 Mbits/sec\n'
  '[ 5] 2.50-3.00 sec 3 MBytes 25.2 Mbits/sec')
 with pytest.raises(AssertionError,match='Incomplete middle'):
  check_thresholds(broken)

def test_malformed_measurement_cannot_be_silently_skipped():
 with pytest.raises(ValueError,match='Unrecognized interval'):
  parser('[ 5] 0.00-1.00 sec 3 MBytes 25.2 Mbits/sec\n'
   '[ 5] 1.00-2.00 sec BROKEN 1 Mbits/sec')

@pytest.mark.parametrize('transfer',['2.00','1.99'])
def test_transfer_must_be_strictly_greater_than_two_mib(transfer):
 with pytest.raises(AssertionError,match='Transfer <= 2 MiB'):
  check_thresholds(measurements(transfer=transfer))

def test_decimal_megabytes_do_not_weaken_mib_threshold():
 with pytest.raises(AssertionError,match='Transfer <= 2 MiB'):
  check_thresholds(measurements(transfer='1.93'))

def test_bitrate_must_be_strictly_greater_than_twenty_mbits():
 with pytest.raises(AssertionError,match='Bitrate <= 20 Mbit/s'):
  check_thresholds(measurements(bitrate='20.0'))

def test_interval_gap_is_not_success():
 rows=measurements();rows[1]['StartSeconds']=1.5
 with pytest.raises(AssertionError,match='Gap or overlap'):
  complete_intervals(rows)

def test_positive_full_measurement_passes():
 assert len(check_thresholds(measurements()))==3
