#include <curl/curl.h>
#include <stdio.h>
#include <string>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <list>
#include <iostream>

#define LOCKADD(var, n) \
do \
{ \
	pthread_mutex_lock(&mutex); \
	var += (n); \
	pthread_mutex_unlock(&mutex); \
	printf("comets: %d, heartbeats: %d\n", comets, heartbeats); \
	printf("%lld bytes moved\n", bytesmoved); \
} while (0);

#define HOST "http://localhost:8000"

using namespace std;

struct threadargs
{
	char *key;
	CURL *curl;
};

bool quit = false;
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
int comets = 0;
int heartbeats = 0;
long long bytesmoved = 0;

size_t movedata(void *ptr, size_t size, size_t n, string *stream)
{
	int len = stream->length();
	stream->append((char *) ptr, size * n);

	int copied = (stream->length() - len);
	LOCKADD(bytesmoved, copied);
	return copied;
}

string fetch(CURL *curl, string url, string post = "")
{
	string data;

	if (post != "")
	{
		curl_easy_setopt(curl, CURLOPT_POST, 1L);
		curl_easy_setopt(curl, CURLOPT_POSTFIELDS, (void *) post.c_str());
	}
	else
	{
		curl_easy_setopt(curl, CURLOPT_HTTPGET, 1L);
	}
	curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
	curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
	curl_easy_setopt(curl, CURLOPT_ENCODING, "");
	curl_easy_setopt(curl, CURLOPT_TIMEOUT, 0L);
	curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 0L);
	curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, movedata);
	curl_easy_setopt(curl, CURLOPT_WRITEDATA, &data);
	if (curl_easy_perform(curl) != 0)
	{
		printf("Huh, failed to fetch <%s>!\n", url.c_str());
	}

	return data;
}

void *heartbeat(void *args)
{
	struct threadargs realargs = *(struct threadargs *) args;
	string url = HOST "/tcp/";
	url.append((char *) realargs.key);
	delete[] (char *) realargs.key;
	url.append("?nocache=0.43030367994910257");
	string res = fetch(realargs.curl, url, string("11,114,data020,bG9jYWxob3N0OjQ3NDcK"));
	if (res != "OK")
	{
		printf("Response was not \"OK\"!: %s\n", res.c_str());
	}

	char buf[21];
	char buf2[21];
	char buf3[21];
	int t = 2;
	int i = 2;
	url.append("&ack=");

	while (!quit)
	{
		sleep(40);
		t += 40;

		int len = snprintf(buf2, 21, "%d", i);
		snprintf(buf, 21, "%d", 10 + len);
		string postdata;
		postdata.append(buf);
		postdata.append(",");
		postdata.append(buf2);
		postdata.append("14,data020,bG9jYWxob3N0OjQ3NDcK");
		snprintf(buf3, 21, "%d", t);
		res = fetch(realargs.curl, url + buf3, postdata);
		if (res != "OK")
		{
			printf("Response was not \"OK\"!: %s\n", res.c_str());
		}

		i++;
	}
	LOCKADD(heartbeats, -1);
	printf("Ok, keepalive killed.\n");

	curl_easy_cleanup(realargs.curl);
	delete (struct threadargs *) args;

	pthread_exit(NULL);
}

void *comet(void *args)
{
	struct threadargs realargs = *(struct threadargs *) args;
	string url = HOST "/tcp/";
	url.append((char *) realargs.key);
	delete[] (char *) realargs.key;
	url.append("/xhrstream?nocache=0.43030367994910257&ack=2");
	printf("Fetching <%s>\n", url.c_str());
	string res = "";
	while (!quit)
	{
		res += fetch(realargs.curl, url);
	}
	printf("Fetch returned, we should probably clean up now.\n%s", res.c_str());
	LOCKADD(comets, -1);

	curl_easy_cleanup(realargs.curl);
	delete (struct threadargs *) args;

	pthread_exit(NULL);
}

int main(int argc, char *argv[])
{
	if (argc != 2)
	{
		printf("Usage: ./cometsim clients\n");
		exit(-2);
	}

	if (curl_global_init(CURL_GLOBAL_ALL) != 0)
	{
		printf("Uh oh, curl didn't init...\n");
		exit(-1);
	}

	list<pthread_t> threads;
	list<pthread_t> blocking_threads;

	int clients = atoi(argv[1]);
	printf("Creating %d clients\n", clients);
	for (int i = 0; i < clients; i++)
	{
		CURL *curl = curl_easy_init();
		pthread_t t = NULL;
		struct threadargs *args = new struct threadargs;
		args->curl = curl;

		string key = fetch(curl, string(HOST "/tcp?nocache=0.43030367994910257"));
		printf("got key: %s\n", key.c_str());
		args->key = new char[key.length() + 1];
		strncpy(args->key, key.c_str(), key.length() + 1);
		pthread_create(&t, NULL, heartbeat, (void *) args);
		threads.push_back(t);
		LOCKADD(heartbeats, 1);

		args = new struct threadargs;
		curl = curl_easy_init();
		args->curl = curl;
		args->key = new char[key.length() + 1];
		strncpy(args->key, key.c_str(), key.length() + 1);
		t = NULL;
		pthread_create(&t, NULL, comet, (void *) args);
		blocking_threads.push_back(t);
		LOCKADD(comets, 1);

		printf("client %d created\n", i);
		/*
		if (i%100 == 0)
		{
			printf("pausing...\n");
			sleep(1);
		}
		*/
	}

	string dummy;
	cin >> dummy;
	printf("Ok, cleaning up, this will take about 2 minutes.\n");
	quit = true;

	for (list<pthread_t>::iterator i = threads.begin(); i != threads.end(); i++)
	{
		pthread_join(*i, NULL);
	}
	printf("All keepalive threads reaped, remaining threads should follow within ~40s.\n");

	for (list<pthread_t>::iterator i = blocking_threads.begin(); i != blocking_threads.end(); i++)
	{
		pthread_join(*i, NULL);
	}

	curl_global_cleanup();

	return 0;
}
