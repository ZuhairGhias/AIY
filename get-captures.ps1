#copy over the captures
scp pi:~/MyPy/captures/* ./captures/
if ($?) {
  # remove files that we copied over
  ssh pi 'rm ~/MyPy/captures/*'
}
