## AAUSAT3 libpycsp makefile
#gcc  -shared -Wl,-soname,libpycsp.so -o libpycsp.so csp_if_can.o -Wl,--whole-archive ../../../../lib/bin/x86/libcsp.a -Wl,--no-whole-archive -lpthread -lrt

TARGET = libpycsp.so
OUTDIR = .
CC = gcc
LD = gcc
SZ = size

# Compiler flags
CFLAGS = -Wall -std=gnu99 -O2 -D_GNU_SOURCE -fPIC #-Werror

# Linker flags
ARCHIVES = ../../../../lib/bin/x86/libcsp.a
LDFLAGS = -shared -Wl,-soname,$(TARGET) -Wl,--whole-archive $(ARCHIVES) -Wl,--no-whole-archive

## Include Directories
INCLUDES = -I../../../../lib/libcsp/include

# Libraries
LIBDIR = -L../../../../lib/bin/x86
LIBS = -lpthread -lrt

## Objects that must be built in order to archive
#SOURCES = csp_if_can.c
OBJECTS=$(SOURCES:.c=.o)

# Define PHONY targets
.PHONY: all clean size

## Default target
all: $(SOURCES) $(TARGET) size

## Compile
.c.o:
	$(CC) $(INCLUDES) $(CFLAGS) -c $< -o $@

## Create shared lib
$(TARGET): $(OBJECTS) $(ARCHIVES)
	$(LD) $(LDFLAGS) $(LIBS) -o $(TARGET) $(OBJECTS) 
	
size:
	$(SZ) -t $(TARGET)

## Clean target
clean:
	-rm -rf $(OBJECTS) $(TARGET)
