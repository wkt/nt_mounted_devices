/**
# _*_ coding: utf-8 _*_
#
# @File : dos_disk_id.c
# @Time : 2022-04-21 20:26
# Copyright (C) 2022 WeiKeting<weikting@gmail.com>. All rights reserved.
# @Description : Read disk id for MBR disk without root
#
#
**
*/

#include <string.h>
#include <stdio.h>
#include <sys/stat.h>
#include <errno.h>
#include <unistd.h>
#include <libproc.h>

inline static void usage()
{
    fprintf(stderr,"Usage: \r\n    dos_disk_id disk_path\r\n");
}

/**
    Change process's user id to @uid
**/
inline static int try_seteuid(uid_t uid)
{
    int ret;
    char path[PROC_PIDPATHINFO_MAXSIZE] = {0};

    if (uid == getuid())
        return 0;

    ret = proc_pidpath (getpid(), path, sizeof(path)-1);
    if ( ret <= 0 ) {
        fprintf(stderr, "proc_pidpath(): %s\n", strerror(errno));
        return -1;
    }

    struct stat sb;
    if (stat(path,&sb) < 0){
        fprintf(stderr,"stat(): %s\r\n",strerror(errno));
        return -1;
    }
    if(getuid() != uid && S_ISUID & sb.st_mode && sb.st_uid == uid){
        /** change user to root if allowed **/
        if(seteuid(0)<0){
            fprintf(stderr,"seteuid(): %s\r\n",strerror(errno));
            return -1;
        }
        if(setuid(uid)<0){
            fprintf(stderr,"setuid(): %s\r\n",strerror(errno));
            return -1;
        }
    }
    return 0;
}

static int read_disk_id(const char *path)
{
    struct stat sb;
    if (stat(path,&sb) < 0){
        fprintf(stderr,"stat(): %s\r\n",strerror(errno));
        return -1;
    }
    if(! S_ISBLK(sb.st_mode)){
        fprintf(stderr,"%s: must be a block file\r\n", path);
        return -1;
    }

    try_seteuid(0);

    FILE *fp;
    fp = fopen(path,"rb");
    if(fp == NULL){
        fprintf(stderr,"fopen(%s): %s\r\n",path,strerror(errno));
        return -1;
    }
    unsigned char _id[4];
    fseek(fp,440,SEEK_SET);
    fread(_id,1,sizeof(_id),fp);
    fclose(fp);

    fprintf(stdout,"%s: ",path);
    for(int i=sizeof(_id)-1;i>=0;i--){
        fprintf(stdout,"%0x",_id[i]);
    }
    fprintf(stdout,"\r\n");
    return 0;
}

int main(int argc,char **argv)
{
    int i = 1;
    if(argc < 2){
        usage();
        return 1;
    }
    for(;i<argc;i++){
        if(read_disk_id(argv[i]) < 0){
            return 2;
        }
    }
    return 0;
}