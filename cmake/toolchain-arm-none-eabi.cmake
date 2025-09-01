include(CMakeForceCompiler)

# The Generic system name is used for embedded targets (targets without OS) in
# CMake
set( CROSS_COMPILE arm-none-eabi- )
set( CMAKE_SYSTEM_NAME          Generic )
set( CMAKE_SYSTEM_PROCESSOR     arm )
set( ARCH arm )

set(CMAKE_C_COMPILER ${CROSS_COMPILE}gcc)
set(CMAKE_CXX_COMPILER ${CROSS_COMPILE}g++)

set(CMAKE_LINKER ${CROSS_COMPILE}ld)     
set(CMAKE_OBJCOPY ${CROSS_COMPILE}objcopy)    

set(CMAKE_C_LINK_EXECUTABLE
        "<CMAKE_C_COMPILER>   <CMAKE_C_LINK_FLAGS> <LINK_FLAGS> <OBJECTS>  -o <TARGET> <LINK_LIBRARIES>")
set(CMAKE_CXX_LINK_EXECUTABLE
        "<CMAKE_CXX_COMPILER>  <CMAKE_CXX_LINK_FLAGS> <LINK_FLAGS>  <OBJECTS>  -o <TARGET> <LINK_LIBRARIES>")



message(STATUS "CMAKE_C_COMPILER: ${CMAKE_C_COMPILER}")
message(STATUS "CMAKE_CXX_COMPILER: ${CMAKE_CXX_COMPILER}")


# To build the tests, we need to set where the target environment containing
# the required library is. On Debian-like systems, this is
# /usr/ arm-none-eabi-.
SET(CMAKE_FIND_ROOT_PATH ${ARM_SYSROOT_PATH})
# search for programs in the build host directories
SET(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
# for libraries and headers in the target directories
SET(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
SET(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)

# We must set the OBJCOPY setting into cache so that it's available to the
# whole project. Otherwise, this does not get set into the CACHE and therefore
# the build doesn't know what the OBJCOPY filepath is
set(CMAKE_OBJCOPY ${CROSS_COMPILE}objcopy
	    CACHE FILEPATH "The toolchain objcopy command " FORCE )


set(ARCH_FLAGS "-mthumb -mcpu=cortex-m55 -mfloat-abi=hard -mcmse")

set(OPT_FLAGS "-Wall -ffunction-sections -fdata-sections -fstack-usage -flax-vector-conversions -specs=nano.specs -O3")

set(COMMON_FLAGS "${DEBUG_FLAGS} ${OPT_FLAGS} ${ARCH_FLAGS} ")


set( CMAKE_C_FLAGS "${CMAKE_C_FLAGS}" CACHE STRING "" )
set( CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}" CACHE STRING "" )
set( CMAKE_ASM_FLAGS "${CMAKE_C_FLAGS}" CACHE STRING "" )


set( CMAKE_C_FLAGS "${COMMON_FLAGS} ${CMAKE_C_FLAGS} -std=gnu11" )
set( CMAKE_CXX_FLAGS "${COMMON_FLAGS}  ${CMAKE_CXX_FLAGS} -std=c++17 -fno-rtti -fno-exceptions -fno-threadsafe-statics -nostdlib" )
set( CMAKE_ASM_FLAGS " ${COMMON_FLAGS}  ${CMAKE_ASM_FLAGS}-x assembler-with-cpp")

if(DEFINED ENV{WE2_SDK_PATH})
	set(WE2_SDK_PATH $ENV{WE2_SDK_PATH})
endif()
