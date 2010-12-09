#include <stdio.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/ip.h>
#include <netdb.h>
#include <fcntl.h>
#include <errno.h>
#include <list>
#include <unistd.h>
#include <string>
#include <string.h>
#include <stdlib.h>
#include <signal.h>

#define LOCKADD(var, n) \
do \
{ \
	pthread_mutex_lock(&mutex); \
	var += (n); \
	pthread_mutex_unlock(&mutex); \
} while (0);

using namespace std;

const unsigned int bufsize = 1024*8;
bool quit = false;
int pipes[2];
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
long long bytesmoved = 0;

bool safewrite(int sock, char *msg, int len, bool ispipe = false)
{
	int i = 0;

	int moved = len;
	while (len > 0)
	{
		int s = (len > bufsize ? bufsize : len);
		int ret = write(sock, &msg[i], s);
		if (ret >= 0)
		{
			len -= ret;
			i += ret;
			//printf("%s %d: wrote %d bytes (%d remaining)\n", (ispipe ? "pipe" : "client"), sock, s, len);
		}
		else if (errno == EPIPE)
		{
			printf("%s %d: disconnect\n", (ispipe ? "pipe" : "client"), sock);
			printf("ret = %d\n", close(sock));
			break;
		}
		else if (errno == EBADF)
		{
			printf("%s %d: reaping fd\n", (ispipe ? "pipe" : "client"), sock);
			printf("ret = %d\n", close(sock));

			return false;
		}
		else
		{
			printf("%s %d: write() threw us an error (%d, errno = %d)\n", (ispipe ? "pipe" : "client"), sock, ret, errno);
			printf("%s %d: error %d = %s\n", (ispipe ? "pipe" : "client"), sock, errno, strerror(errno));
			usleep(5000);
		}
	}
	LOCKADD(bytesmoved, moved);

	return true;
}

void handle_signal(int num)
{
	printf("caught signal %d\n", num);

	switch (num)
	{
		case SIGINT:
		case SIGQUIT:
			quit = 1;
			break;
		default:
			break;
	}
}

void *handle_accepts(void *sockptr)
{
	int *ptrcopy = (int *) sockptr;
	int sock = *(int *) sockptr;
	delete ptrcopy;
	int conn;
	string msg;

	while (!quit)
	{
		if ((conn = accept(sock, NULL, NULL)) != -1)
		{
			printf("client %d connected\n", conn);
			fcntl(conn, F_SETFL, O_NONBLOCK);
			safewrite(pipes[1], (char *) &conn, sizeof(conn), true);
		}
		else
		{
			printf("Hmm, that's strange, accept() failed, errno = %d (%s)\n", errno, strerror(errno));
		}
	}

	pthread_exit(NULL);
}

int main(void)
{
	struct sigaction sigh;

	sigh.sa_handler = SIG_IGN;
	sigh.sa_flags = 0;
	sigaction(SIGPIPE, &sigh, NULL);

	sigh.sa_handler = &handle_signal;
	sigaction(SIGINT, &sigh, NULL);
	sigaction(SIGQUIT, &sigh, NULL);

	int sock;
	protoent *p = getprotobyname("TCP");
	if ((sock = socket(AF_INET, SOCK_STREAM, p->p_proto)) == -1)
	{
		printf("Couldn't create socket! (%s)\n", strerror(errno));
		exit(-1);
	}

	setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, (const void *) true, sizeof(true));
	// accepts should block
	//fcntl(sock, F_SETFL, O_NONBLOCK);

	sockaddr_in addr;
	addr.sin_family = AF_INET;
	addr.sin_port = htons(4747);
	addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	if (bind(sock, (const sockaddr *) &addr, sizeof(addr)) != 0)
	{
		printf("Couldn't bind! (%s)\n", strerror(errno));
		exit(-2);
	}

	if (listen(sock, 512) != 0)
	{
		printf("Couldn't listen!\n");
		exit(-3);
	}

	if (pipe(pipes) != 0)
	{
		printf("Couldn't create pipes!\n");
		exit(-4);
	}
	fcntl(pipes[0], F_SETFL, O_NONBLOCK);

	pthread_t accept_thread;
	int *sockptr = new int;
	*sockptr = sock;
	int r = pthread_create(&accept_thread, NULL, handle_accepts, (void *) sockptr);
	if (r != 0)
	{
		printf("Couldn't create accept thread, errno = %d (%s)\n", r, strerror(r));
		exit(-4);
	}

	printf("Init seemed fine, waiting for connections...\n");

	list<int> clients;

	while (!quit)
	{
		//block on message reading
		int conn;

		printf("%ld clients, %lld bytes moved\n", clients.size(), bytesmoved);

		int buf[bufsize/sizeof(int)];
		r = read(pipes[0], buf, bufsize);
		if (r > 0)
		{
			printf("Read %d bytes from accept thread\n", r);
			for (int i = 0; i < r/sizeof(int); i++)
			{
				clients.push_back(buf[i]);
				printf("client %d: queued\n", buf[i]);
			}

			int rem = r%sizeof(int);
			if (rem != 0)
			{
				printf("This should never happen. But, if it does, it's not impossible to work around, we just don't do that yet. (rem was %d)\n", rem);
				exit(-5);
				//stuff the remaining bits somewhere for next time
			}
		}

		char msg[50];
		int len = snprintf(msg, 50, "it's a message! %d", rand()%1000);
		for (list<int>::iterator i = clients.begin(); i != clients.end(); )
		{
			if (!safewrite(*i, msg, len))
			{
				i = clients.erase(i);
			}
			else
			{
				i++;
			}
		}

		//usleep(10000);
		sleep(1);
	}

	for (list<int>::iterator i = clients.begin(); i != clients.end(); i++)
	{
		printf("client %d: terminating: %d\n", *i, close(*i));
	}
	printf("socket closed: %d\n", close(sock));

	/* TODO: handle write buffer full more intelligently in safewrite (for both accept thread and main thread), and don't block on message reading forever (use the pipe trick) */

	return 0;
}
