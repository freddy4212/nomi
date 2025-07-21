@page new_operation_types Implement new types of operations
@brief Guide for implementing new types of operations

@note If there is an operation type that matches your needs, you might instead extend this
operation type with one operation, which is easier to do than define new operation types.

@note While reading this guide, feel free to inspect the existing operations in the `include/` and
`src/` source directories complete examples.

@note This process is the same if you wish to implement new operations inside your application or
for contributing new operations to libmpix.

Through these code snippets, replace `<custom>` or `<CUSTOM>` by any name you wish for your type
of operation.

## Create the new type struct

All libmpix operations use a common base defined in @ref mpix_op_h, the @ref mpix_base_op.

- It describes the operation so that it can be selected from a list of operations available.

- It keeps track of the ongoing state of the processing.

For both purpose, new operation types might need extra fields to define more than the basics.
One way to do this in the C language is to define a new structure with the @ref mpix_base_op as
the first field, so that the pointer can be casted between the two.

To reduce repetitive boilerplate, it is possible to add a function pointer field, so that each
individual operation defined with this type has minimal work to do.

For instance:

```c
struct mpix_<custom>_op {
	struct mpix_base_op base;
	void (*<custom>_fn)(/* Anything you need */);
	/* Any other custom fields */
};
```

## Define a helper for more convenient API

Then a wrapper function can convert between the generic operation API and the custom API that you
define for your own operation type.

```c
void mpix_<custom>_op(struct mpix_base_op *base)
{
	/* Get the custom operation by casting it from the base operation */
	struct mpix_<custom>_op *op = (void *)base;

	/* Perform the custom conversion using the convenient API we defined for ourself */
	op-><custom>_fn(/* parameters extracted from `op` and `base` */);

	/* Confirm that the conversion is complete */
	mpix_op_done(base);
}
```

## Add a macro to create operations

Once this is done, to define all the operations with that type, define a macro which exposes only
the fields that the user has to fill, and reduce the amount of typing. For instance:

```c
#define MPIX_REGISTER_<CUSTOM>_OP(id, fn, /* Anything you need */)                                 \
	const struct mpix_<custom>_op mpix_<custom>_op_##id = {                                    \
		.base.name = "<custom>_" #id,                                                      \
		.base.fourcc_src = /* Anything you need */,                                        \
		.base.fourcc_dst = /* Anything you need */,                                        \
		.base.window_size = /* Anything you need */,                                       \
		.base.run = mpix_<custom>_op,                                                      \
		.<custom>_fn = (fn),                                                               \
		/* Anything you need */                                                            \
	}
```

## Add an example operation using these

It is now possible to add new operations with this type in a C source file:

```c
void mpix_<custom>_convert_from_x_to_y(/* Local API you defined for yourself */)
{
	/* Process the input buffer and store it into the output buffer */
}
MPIX_REGISTER_<CUSTOM>_OP(x_to_y, mpix_convert_rgb24_to_rgb332, /* Anything you need */);
```

## Add a table of operations

Every time `MPIX_REGISTER_<CUSTOM>_OP` is added in C file, this will add the operation to a global
list which you can access via `MPIX_LIST_<CUSTOM>_OP`, typically at the bottom of the C file:

```c
static const struct mpix_<custom>_op **mpix_<custom>_op_list =
	(const struct mpix_<custom>_op *[]){MPIX_LIST_<CUSTOM>_OP};
```

## Define an user API searching that table

Finally, you can select which high-level API you wish to expose to the user, so that he can select
an operation from this list.

For instance:

- Format conversion operations would have the destination type as parameter, and the source type
  already known from the previous operation.

- Image filters can take a parameter for the type of filter as well as the level of correction.

- Image compression operations can let the user specify the various levels of the compression.

For each, the structure is typically like this:

```c
int mpix_image_<custom>(struct mpix_image *img, /* Anything you need */)
{
	const struct mpix_<custom>_op *op = NULL;

	/* Loop through every operation of the list to search one that matches the parameters */
	for (size_t i = 0; mpix_<custom>_op_list[i] != NULL; i++) {
		const struct mpix_<custom>_op *tmp = mpix_<custom>_op_list[i];

		if (/* Compare the operation from the list `tmp` with the user specified */) {
			/* We found a matching operation in the list */
			op = tmp;
			break;
		}
	}

	if (op == NULL) {
		MPIX_ERR("<custom> operation not found");
		return mpix_image_error(img, -ENOSYS);
	}

	/* If using a compressed *input* format, you need to change this line */
	return mpix_image_append_uncompressed_op(img, &op->base, sizeof(*op));
}
```

The new custom operation can now be used in the application using the user API.

## Tell genlist.py to also scan this C source

Finishing step is in the the `CMakeLists.txt`, add the C source to the files to scan for
`MPIX_REGISTER_..._OP()` entries:

```cmake
libmpix_add_genlist_source(op_<custom>.c)
```
