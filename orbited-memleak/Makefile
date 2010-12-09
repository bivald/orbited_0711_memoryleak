.PHONY: all clean

all: clshim cometsim

clshim: clshim.cpp
	$(CXX) $(CXXFLAGS) -lpthread -o clshim clshim.cpp

cometsim: cometsim.cpp
	$(CXX) $(CXXFLAGS) -lpthread -lcurl -o cometsim cometsim.cpp

clean:
	rm -f clshim cometsim
