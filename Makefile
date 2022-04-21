## for macOS
dos_disk_id:dos_disk_id.c
	$(CC) dos_disk_id.c -mmacosx-version-min=10.7 -o dos_disk_id
	#chown root dos_disk_id
	#chmod u+s dos_disk_id

clean:
	rm -rf dos_disk_id