# directory declaration
LIB_LIBMPIX_DIR = $(LIBRARIES_ROOT)/libmpix

LIB_LIBMPIX_ASMSRCDIR	= $(LIB_LIBMPIX_DIR) 
LIB_LIBMPIX_CSRCDIR	= $(LIB_LIBMPIX_DIR)/libmpix/src/
LIB_LIBMPIX_CSRCDIR	+= $(LIB_LIBMPIX_DIR)/libmpix/ports/grove_vision_ai2/
LIB_LIBMPIX_INCDIR	= $(LIB_LIBMPIX_DIR)/libmpix/include/
LIB_LIBMPIX_INCDIR	+= $(LIB_LIBMPIX_DIR)/libmpix/include/mpix/

# find all the source files in the target directories
LIB_LIBMPIX_CSRCS = $(call get_csrcs, $(LIB_LIBMPIX_CSRCDIR))
LIB_LIBMPIX_ASMSRCS = $(call get_asmsrcs, $(LIB_LIBMPIX_ASMSRCDIR))

# get object files
LIB_LIBMPIX_COBJS = $(call get_relobjs, $(LIB_LIBMPIX_CSRCS))
LIB_LIBMPIX_ASMOBJS = $(call get_relobjs, $(LIB_LIBMPIX_ASMSRCS))
LIB_LIBMPIX_OBJS = $(LIB_LIBMPIX_COBJS) $(LIB_LIBMPIX_ASMOBJS)

# get dependency files
LIB_LIBMPIX_DEPS = $(call get_deps, $(LIB_LIBMPIX_OBJS))

# extra macros to be defined
LIB_LIBMPIX_DEFINES = -DLIB_LIBMPIX

# genearte library
ifeq ($(LIBMPIX_LIB_FORCE_PREBUILT), y)
override LIB_LIBMPIX_OBJS:=
endif
LIBMPIX_LIB_NAME = liblibmpix.a
LIB_LIBMPIX := $(subst /,$(PS), $(strip $(OUT_DIR)/$(LIBMPIX_LIB_NAME)))

# library generation rule
$(LIB_LIBMPIX): $(LIB_LIBMPIX_OBJS)
	$(TRACE_ARCHIVE)
ifeq "$(strip $(LIB_LIBMPIX_OBJS))" ""
	$(CP) $(PREBUILT_LIB)$(LIBMPIX_LIB_NAME) $(LIB_LIBMPIX)
else
	$(Q)$(AR) $(AR_OPT) $@ $(LIB_LIBMPIX_OBJS)
	$(CP) $(LIB_LIBMPIX) $(PREBUILT_LIB)$(LIBMPIX_LIB_NAME)
endif

# specific compile rules
# user can add rules to compile this middleware
# if not rules specified to this middleware, it will use default compiling rules

# Middleware Definitions
LIB_INCDIR += $(LIB_LIBMPIX_INCDIR)
LIB_CSRCDIR += $(LIB_LIBMPIX_CSRCDIR)
LIB_ASMSRCDIR += $(LIB_LIBMPIX_ASMSRCDIR)

LIB_CSRCS += $(LIB_LIBMPIX_CSRCS)
LIB_CXXSRCS +=
LIB_ASMSRCS += $(LIB_LIBMPIX_ASMSRCS)
LIB_ALLSRCS += $(LIB_LIBMPIX_CSRCS) $(LIB_LIBMPIX_ASMSRCS)

LIB_COBJS += $(LIB_LIBMPIX_COBJS)
LIB_CXXOBJS +=
LIB_ASMOBJS += $(LIB_LIBMPIX_ASMOBJS)
LIB_ALLOBJS += $(LIB_LIBMPIX_OBJS)

LIB_DEFINES += $(LIB_LIBMPIX_DEFINES)
LIB_DEPS += $(LIB_LIBMPIX_DEPS)
LIB_LIBS += $(LIB_LIBMPIX)